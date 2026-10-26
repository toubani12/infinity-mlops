import io
import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from mlflow import MlflowClient

from data.schema import RAW_COLUMNS, TIME
from data.simulate_drift import simulate
from data.storage import list_files
from data.synthetic import generate
from training import retrain as retrain_module
from training.retrain import (
    RetrainSettings,
    build_split,
    load_labeled_predictions,
    partition_prefixes,
    retrain,
    to_training_rows,
)
from training.train import TrainConfig, train

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
PARAMS = {"n_estimators": 60, "max_depth": 3, "learning_rate": 0.2, "eval_metric": "aucpr"}


class ListingS3:
    def __init__(self, page_size: int = 2) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.page_size = page_size

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def list_objects_v2(self, Bucket: str, Prefix: str, ContinuationToken: str = "0") -> dict:
        keys = sorted(k for b, k in self.objects if b == Bucket and k.startswith(Prefix))
        start = int(ContinuationToken)
        page = keys[start : start + self.page_size]
        more = start + self.page_size < len(keys)
        return {
            "Contents": [{"Key": key} for key in page],
            "IsTruncated": more,
            "NextContinuationToken": str(start + self.page_size),
        }


def config(model_name: str) -> TrainConfig:
    return TrainConfig(
        params=PARAMS,
        experiment="fraud-xgb-test",
        model_name=model_name,
        early_stopping_rounds=10,
        latency_samples=20,
        retrain={"eval_share": 0.3, "min_eval_frauds": 10},
    )


def prediction_log(base: pd.DataFrame, start: datetime, rows: int, seed: int) -> pd.DataFrame:
    """`rows` labeled transactions scored evenly from `start` to NOW."""
    rate = rows / (NOW - start).total_seconds()
    return simulate(
        base, "sudden", rows=rows, fraud_rate=0.05, rate=rate, start=start, seed=seed
    ).assign(fraud_score=0.1, model_version="1")


def write_partitions(log: pd.DataFrame, root) -> None:
    for (day, hour), part in log.groupby(
        [log["timestamp"].dt.strftime("%Y-%m-%d"), log["timestamp"].dt.strftime("%H")]
    ):
        folder = root / f"dt={day}" / f"hour={hour}"
        folder.mkdir(parents=True, exist_ok=True)
        part.to_parquet(folder / "part-0.parquet", index=False)


def test_settings_from_env_defaults_and_validation() -> None:
    settings = RetrainSettings.from_env({"RUN_ID": "abc12345-run"})
    assert settings.window_days == 7.0
    assert settings.data_uri == "s3://datasets/raw/creditcard.parquet"
    assert settings.predictions_uri == "s3://predictions/"
    assert settings.config_path().is_file()
    with pytest.raises(ValueError, match="RUN_ID"):
        RetrainSettings.from_env({"RUN_ID": " "})
    with pytest.raises(ValueError, match="WINDOW_DAYS"):
        RetrainSettings.from_env({"RUN_ID": "x", "WINDOW_DAYS": "0"})
    custom = RetrainSettings.from_env({"RUN_ID": "x", "WINDOW_DAYS": "2.5", "DATA_URI": "/d.csv"})
    assert (custom.window_days, custom.data_uri) == (2.5, "/d.csv")


def test_partition_prefixes_cover_every_day_of_the_window() -> None:
    prefixes = partition_prefixes("s3://predictions/", NOW - timedelta(days=2), NOW)
    assert prefixes == [
        "s3://predictions/dt=2026-10-24/",
        "s3://predictions/dt=2026-10-25/",
        "s3://predictions/dt=2026-10-26/",
    ]


def test_labeled_predictions_inside_window_only(tmp_path, raw_frame) -> None:
    log = prediction_log(raw_frame, NOW - timedelta(days=3), rows=400, seed=1)
    log.loc[380:389, "label"] = pd.NA
    log.loc[379, "v3"] = float("nan")
    duplicate = log.iloc[[390]].assign(label=1 - int(log.loc[390, "label"]))
    write_partitions(pd.concat([log, duplicate], ignore_index=True), tmp_path)

    since = NOW - timedelta(days=2)
    loaded = load_labeled_predictions(str(tmp_path), since, NOW)
    inside = log[log["timestamp"] >= since]
    expected = inside["label"].notna() & inside["v3"].notna()
    assert len(loaded) == int(expected.sum())
    assert loaded["transaction_id"].is_unique
    assert loaded["timestamp"].min() >= since
    by_id = loaded.set_index("transaction_id")["label"]
    assert by_id[log.loc[390, "transaction_id"]] == duplicate["label"].iloc[0]


def test_labeled_predictions_from_paged_s3(raw_frame) -> None:
    s3 = ListingS3()
    log = prediction_log(raw_frame, NOW - timedelta(hours=10), rows=60, seed=2)
    for hour, part in log.groupby(log["timestamp"].dt.strftime("%H")):
        buffer = io.BytesIO()
        part.to_parquet(buffer, index=False)
        s3.put_object(
            "predictions", f"dt=2026-10-26/hour={hour}/part-{hour}.parquet", buffer.getvalue()
        )
    s3.put_object("predictions", "dt=2026-10-26/_SUCCESS", b"")
    assert len(list_files("s3://predictions/dt=2026-10-26/", client=s3)) > 2
    loaded = load_labeled_predictions("s3://predictions", NOW - timedelta(days=1), NOW, s3)
    assert len(loaded) == int(log["label"].notna().sum())


def test_no_predictions_gives_an_empty_frame(tmp_path) -> None:
    loaded = load_labeled_predictions(str(tmp_path / "absent"), NOW - timedelta(days=7), NOW)
    assert loaded.empty
    assert list(to_training_rows(loaded, 10.0).columns) == RAW_COLUMNS


def test_training_rows_follow_the_base_timeline(raw_frame) -> None:
    log = prediction_log(raw_frame, NOW - timedelta(hours=1), rows=50, seed=3).dropna()
    rows = to_training_rows(log, time_origin=1_000.0)
    assert list(rows.columns) == RAW_COLUMNS
    assert rows[TIME].iloc[0] == 1_001.0 and rows[TIME].is_monotonic_increasing
    assert rows["class"].dtype == "int64"


def test_split_tests_on_the_newest_labeled_slice(raw_frame) -> None:
    base = raw_frame.sort_values(TIME).reset_index(drop=True)
    log = prediction_log(raw_frame, NOW - timedelta(days=1), rows=1_000, seed=4).dropna()
    recent = to_training_rows(log, float(base[TIME].max()))
    split, eval_slice = build_split(base, recent, config("unused"))
    assert eval_slice == "recent"
    assert split.train[TIME].max() < split.test[TIME].min()
    assert len(split.test) == pytest.approx(0.3 * len(recent), abs=2)
    assert len(split.train) + len(split.valid) + len(split.test) == len(base) + len(recent)


def test_split_falls_back_without_enough_labeled_frauds(raw_frame) -> None:
    log = prediction_log(raw_frame, NOW - timedelta(days=1), rows=100, seed=5).dropna()
    recent = to_training_rows(log.assign(label=0), float(raw_frame[TIME].max()))
    split, eval_slice = build_split(raw_frame, recent, config("unused"))
    assert eval_slice == "holdout"
    assert split.test[TIME].max() == recent[TIME].max()


@pytest.fixture(scope="module")
def retrained(tracking, raw_frame, tmp_path_factory):
    name = "fraud-xgb-retrain"
    root = tmp_path_factory.mktemp("retrain")
    reference_root = str(root / "reference")
    train(raw_frame, config(name), bootstrap=True, reference_root=reference_root)
    data = root / "creditcard.csv"
    generate(rows=4_000, fraud_rate=0.03, seed=7).to_csv(data, index=False)
    write_partitions(prediction_log(raw_frame, NOW - timedelta(days=2), 3_000, seed=6), root / "p")
    settings = RetrainSettings(
        run_id="run-retrain-1", data_uri=str(data), predictions_uri=str(root / "p")
    )
    return retrain(settings, config(name), now=NOW, reference_root=reference_root)


def test_retrain_registers_a_tagged_challenger(retrained) -> None:
    client = MlflowClient()
    training = retrained.training
    assert retrained.eval_slice == "recent" and retrained.labeled_rows > 2_000
    found = client.search_model_versions(
        f"name='{training.model_name}' and tag.run_id='run-retrain-1'"
    )
    assert [str(v.version) for v in found] == [training.version] == ["2"]
    tags = found[0].tags
    assert tags["data_window"].startswith("days=7;from=2026-10-19T12:00Z;to=2026-10-26T12:00Z")
    assert tags["reference_uri"] == training.reference_uri
    assert pd.read_parquet(training.reference_uri)["model_version"].unique().tolist() == ["2"]
    challenger = client.get_model_version_by_alias(training.model_name, "challenger")
    assert str(challenger.version) == "2"
    assert str(client.get_model_version_by_alias(training.model_name, "champion").version) == "1"


def test_retrain_logs_champion_metrics_and_gate(retrained) -> None:
    run = MlflowClient().get_run(retrained.training.mlflow_run_id)
    assert {"champion_pr_auc", "champion_recall_at_p90", "champion_p95_latency_ms"} <= set(
        run.data.metrics
    )
    assert run.data.tags["gate_passed"] == str(retrained.training.gate.passed).lower()
    assert run.data.tags["gate_reasons"] == retrained.training.gate.summary()
    assert run.data.tags["eval_slice"] == "recent"
    assert retrained.training.champion_version == "1"


def test_main_exits_zero_and_prints_the_outcome(tracking, tmp_path, monkeypatch, capsys) -> None:
    data = tmp_path / "creditcard.csv"
    generate(rows=3_000, fraud_rate=0.03, seed=9).to_csv(data, index=False)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        json.dumps({"experiment": "fraud-xgb-test", "params": PARAMS, "latency_samples": 5})
    )
    monkeypatch.setenv("MODEL_NAME", "fraud-xgb-retrain-cli")
    monkeypatch.setenv("REFERENCE_ROOT", str(tmp_path / "reference"))
    env = {
        "RUN_ID": "run-cli",
        "TRAIN_CONFIG": str(config_file),
        "DATA_URI": str(data),
        "PREDICTIONS_URI": str(tmp_path / "empty"),
    }
    assert retrain_module.main(env) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run_id"] == "run-cli" and out["version"] == "1"
    assert out["eval_slice"] == "holdout" and out["labeled_rows"] == 0
    assert out["gate_passed"] is True and out["champion_version"] is None


def test_gate_rejects_a_worse_challenger_without_failing_the_job(
    tracking, raw_frame, tmp_path, monkeypatch, capsys
) -> None:
    name = "fraud-xgb-retrain-worse"
    monkeypatch.setenv("MODEL_NAME", name)
    monkeypatch.setenv("REFERENCE_ROOT", str(tmp_path / "reference"))
    train(raw_frame, config(name), bootstrap=True)
    data = tmp_path / "creditcard.csv"
    raw_frame.to_csv(data, index=False)
    weak = {"n_estimators": 1, "max_depth": 1, "learning_rate": 0.01, "eval_metric": "aucpr"}
    config_file = tmp_path / "weak.yaml"
    config_file.write_text(
        json.dumps({"experiment": "fraud-xgb-test", "params": weak, "latency_samples": 5})
    )
    env = {"RUN_ID": "run-worse", "TRAIN_CONFIG": str(config_file), "DATA_URI": str(data)}
    assert retrain_module.main(env | {"PREDICTIONS_URI": str(tmp_path / "none")}) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["gate_passed"] is False and out["champion_version"] == "1"
    assert any("is not above champion" in reason for reason in out["gate_reasons"])
    client = MlflowClient()
    version = client.get_model_version(name, out["version"])
    tags = client.get_run(version.run_id).data.tags
    assert tags["gate_passed"] == "false"
    assert "is not above champion" in tags["gate_reasons"]
    assert str(client.get_model_version_by_alias(name, "champion").version) == "1"
    assert str(client.get_model_version_by_alias(name, "challenger").version) == "2"


def test_main_fails_on_technical_errors(tmp_path) -> None:
    assert retrain_module.main({}) == 1
    broken = tmp_path / "creditcard.txt"
    broken.write_text("not a dataset")
    assert retrain_module.main({"RUN_ID": "r", "DATA_URI": str(broken)}) == 1
