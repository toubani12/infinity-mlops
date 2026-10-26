import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from scipy.stats import ks_2samp
from xgboost import XGBClassifier

from data import simulate_drift
from data.ingest import normalize_columns, prepare
from data.schema import FEATURES
from data.simulate_drift import simulate, to_event
from data.synthetic import generate
from training.evaluate import pr_auc

CONTRACTS = Path(__file__).resolve().parents[2] / "libs" / "contracts"
START = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def data() -> pd.DataFrame:
    return normalize_columns(generate(rows=40_000, fraud_rate=0.01, seed=3))


@pytest.fixture(scope="module")
def reference(data) -> pd.DataFrame:
    return simulate(data, "sudden", rows=3_000, magnitude=0.0, concept=0.0, seed=1, start=START)


def drift_share(reference: pd.DataFrame, current: pd.DataFrame) -> float:
    drifted = [f for f in FEATURES if ks_2samp(reference[f], current[f].dropna()).pvalue < 0.05]
    return len(drifted) / len(FEATURES)


def psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    expected = np.histogram(reference, edges)[0] / len(reference) + 1e-6
    actual = np.histogram(current, edges)[0] / len(current) + 1e-6
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def test_stable_replay_does_not_drift(data, reference) -> None:
    replay = simulate(data, "sudden", rows=3_000, magnitude=0.0, concept=0.0, seed=2)
    assert drift_share(reference, replay) <= 0.3


def test_sudden_drift_moves_features_after_the_change_point(data, reference) -> None:
    replay = simulate(data, "sudden", rows=3_000, change_at=0.5, seed=2)
    before, after = replay.iloc[:1_500], replay.iloc[1_500:]
    assert drift_share(reference, before) <= 0.3
    assert drift_share(reference, after) > 0.3
    assert psi(reference["v14"], after["v14"]) > 0.2


def test_gradual_drift_grows_over_the_replay(data, reference) -> None:
    replay = simulate(data, "gradual", rows=3_000, seed=2)
    early, late = replay.iloc[:600], replay.iloc[-600:]
    assert psi(reference["v4"], early["v4"]) < psi(reference["v4"], late["v4"])
    assert drift_share(reference, replay) > 0.3


def test_concept_drift_lowers_pr_auc(data) -> None:
    train = prepare(data)
    model = XGBClassifier(n_estimators=80, max_depth=3, learning_rate=0.2)
    model.fit(train[FEATURES], train["class"])
    clean = simulate(data, "sudden", rows=4_000, magnitude=0, concept=0, fraud_rate=0.05, seed=4)
    drifted = simulate(data, "sudden", rows=4_000, change_at=0, fraud_rate=0.05, seed=4)

    def score(frame: pd.DataFrame) -> float:
        return pr_auc(frame["label"].astype(int), model.predict_proba(frame[FEATURES])[:, 1])

    assert score(clean) - score(drifted) > 0.05


def test_missing_feature_incident(data) -> None:
    replay = simulate(data, "data-incident", incident="missing", incident_share=0.6, seed=2)
    for feature in simulate_drift.MISSING:
        assert replay[feature].isna().mean() == pytest.approx(0.6, abs=0.05)
    assert replay["v1"].notna().all()


def test_out_of_domain_incident(data, reference) -> None:
    replay = simulate(data, "data-incident", incident="out-of-domain", incident_share=0.2, seed=2)
    high = reference[FEATURES].max()
    outside = (replay[FEATURES] > high + 0.1 * (high - reference[FEATURES].min())).any(axis=1)
    assert outside.mean() == pytest.approx(0.2, abs=0.03)


def test_labels_delay_and_identity(data) -> None:
    replay = simulate(data, "gradual", rows=1_000, rate=100, labels_delay=2.5, start=START)
    assert replay["transaction_id"].is_unique
    assert replay["timestamp"].iloc[0] == START
    assert replay["timestamp"].iloc[-1] == pd.Timestamp("2026-10-26T10:00:09.990Z")
    assert replay["label"].isna().sum() == 250
    assert replay["label"].iloc[:750].notna().all()
    unlabeled = simulate(data, "gradual", rows=100, labels_delay=None)
    assert unlabeled["label"].isna().all()


def test_invalid_arguments(data) -> None:
    with pytest.raises(ValueError):
        simulate(data, "storm")
    with pytest.raises(ValueError):
        simulate(data, "data-incident", incident="fire")


class FakeProducer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict, bytes]] = []
        self.state = "new"

    async def start(self) -> None:
        self.state = "started"

    async def send(self, topic: str, value: bytes, key: bytes) -> None:
        self.sent.append((topic, json.loads(value), key))

    async def flush(self) -> None:
        pass

    async def stop(self) -> None:
        self.state = "stopped"


def test_events_follow_the_raw_contract(data) -> None:
    schema = json.loads((CONTRACTS / "events" / "transaction.raw.v1.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    replay = simulate(data, "data-incident", rows=200, incident="missing", labels_delay=0.5)
    producer = FakeProducer()
    sent = asyncio.run(simulate_drift.publish(replay, "unused", rate=0, producer=producer))
    assert sent == 200 and producer.state == "stopped"
    for topic, event, key in producer.sent:
        validator.validate(event)
        assert topic == "transaction.raw" and key.decode() == event["transaction_id"]
    assert any("label" in event for _, event, _ in producer.sent)
    assert any("label" not in event for _, event, _ in producer.sent)
    assert to_event(replay.iloc[0].to_dict())["v4"] in (0.0, replay["v4"].iloc[0])


def test_cli_writes_parquet(tmp_path) -> None:
    out = tmp_path / "replay.parquet"
    simulate_drift.main(
        ["--scenario", "sudden", "--data", str(tmp_path / "absent.csv"), "--rows", "300"]
        + ["--out", str(out), "--no-labels"]
    )
    frame = pd.read_parquet(out)
    assert len(frame) == 300 and frame["label"].isna().all()


def test_cli_requires_one_destination() -> None:
    with pytest.raises(SystemExit):
        simulate_drift.main(["--scenario", "sudden"])
