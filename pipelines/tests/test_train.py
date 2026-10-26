import json

import mlflow
import mlflow.xgboost
import pandas as pd
import pytest
import yaml
from mlflow import MlflowClient

from data.schema import FEATURES
from data.synthetic import generate
from registry import reference
from training import train as train_module
from training.train import DEFAULT_CONFIG, TrainConfig, train

PARAMS = {"n_estimators": 60, "max_depth": 3, "learning_rate": 0.2, "eval_metric": "aucpr"}


def small_config(model_name: str) -> TrainConfig:
    return TrainConfig(
        params=PARAMS,
        experiment="fraud-xgb-test",
        model_name=model_name,
        early_stopping_rounds=10,
        latency_samples=20,
    )


@pytest.fixture(scope="module")
def trained(tracking, raw_frame, tmp_path_factory):
    config = small_config("fraud-xgb-train")
    root = str(tmp_path_factory.mktemp("reference"))
    first = train(raw_frame, config, bootstrap=True, reference_root=root)
    second = train(raw_frame, config, window_days=1.5, agent_run_id="run-42", reference_root=root)
    return config, root, first, second


def test_versions_and_aliases(trained) -> None:
    config, _, first, second = trained
    client = MlflowClient()
    assert (first.version, second.version) == ("1", "2")
    assert str(client.get_model_version_by_alias(config.model_name, "champion").version) == "1"
    assert str(client.get_model_version_by_alias(config.model_name, "challenger").version) == "2"


def test_metrics_are_logged(trained) -> None:
    _, _, first, _ = trained
    metrics = MlflowClient().get_run(first.mlflow_run_id).data.metrics
    assert {"pr_auc", "recall_at_p90", "roc_auc", "p95_latency_ms"} <= metrics.keys()
    assert first.metrics.pr_auc > 0.6
    assert 0 < first.metrics.p95_latency_ms < 50
    assert first.gate.passed and first.champion_version is None


def test_second_run_is_compared_with_champion(trained) -> None:
    _, _, _, second = trained
    run = MlflowClient().get_run(second.mlflow_run_id)
    assert {"champion_pr_auc", "champion_recall_at_p90", "champion_p95_latency_ms"} <= set(
        run.data.metrics
    )
    assert run.data.tags["gate_passed"] in {"true", "false"}
    assert run.data.tags["agent_run_id"] == "run-42"
    assert second.champion_version == "1"
    assert len(second.gate.reasons) == 3
    assert int(run.data.params["best_iteration"]) >= 0


def test_version_tags(trained) -> None:
    config, _, _, second = trained
    tags = MlflowClient().get_model_version(config.model_name, "2").tags
    assert tags["run_id"] == "run-42"
    assert tags["data_window"].endswith("days=1.5d")
    assert tags["reference_uri"] == second.reference_uri


def test_reference_follows_the_champion(trained) -> None:
    _, root, _, _ = trained
    current = pd.read_parquet(reference.current_uri(root))
    challenger = pd.read_parquet(reference.versioned_uri("2", root))
    assert list(current.columns) == [*FEATURES, "fraud_score", "label", "model_version"]
    assert set(current["model_version"]) == {"1"}
    assert set(challenger["model_version"]) == {"2"}
    assert current["fraud_score"].between(0, 1).all()


def test_registered_model_loads_by_alias(trained, raw_frame) -> None:
    config, *_ = trained
    model = mlflow.xgboost.load_model(f"models:/{config.model_name}@champion")
    scores = model.predict_proba(raw_frame[FEATURES].head(3))[:, 1]
    assert scores.shape == (3,)


def test_baseline_config_parses() -> None:
    config = TrainConfig.load(DEFAULT_CONFIG)
    assert config.params["tree_method"] == "hist"
    assert config.fractions == (0.7, 0.15, 0.15)
    assert config.max_p95_ms == 50


def test_cli(tracking, tmp_path, monkeypatch, capsys) -> None:
    csv = tmp_path / "creditcard.csv"
    generate(rows=3_000, fraud_rate=0.03, seed=9).to_csv(csv, index=False)
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {"experiment": "fraud-xgb-test", "params": PARAMS, "early_stopping_rounds": 5}
            | {"latency_samples": 5}
        )
    )
    monkeypatch.setenv("MODEL_NAME", "fraud-xgb-cli")
    train_module.main(
        ["--data", str(csv), "--config", str(config), "--bootstrap-champion"]
        + ["--reference-root", str(tmp_path / "ref")]
    )
    result = json.loads(capsys.readouterr().out)
    assert result["model_name"] == "fraud-xgb-cli" and result["version"] == "1"
    assert (tmp_path / "ref" / "reference.parquet").exists()
