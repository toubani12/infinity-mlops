from types import SimpleNamespace

import pytest
from mlflow.exceptions import MlflowException

from agent.tools.registry import ChallengerNotFound, MlflowAliasMover, MlflowMetricsReader

RUN_ID = "5b2c7d8e-9f0a-4b1c-8d2e-3f4a5b6c7d8e"
TRAINING_METRICS = {
    "pr_auc": 0.83,
    "recall_at_p90": 0.68,
    "roc_auc": 0.97,
    "p95_latency_ms": 6.4,
    "champion_pr_auc": 0.71,
    "champion_recall_at_p90": 0.52,
    "champion_p95_latency_ms": 6.1,
}


class FakeMlflowClient:
    def __init__(self, versions=None, metrics=None, tags=None, aliases=None):
        self.versions = versions if versions is not None else [("4", "train-run-4")]
        self.metrics = TRAINING_METRICS if metrics is None else metrics
        self.tags = {"gate_passed": "true", "gate_reasons": "beats champion"} | (tags or {})
        self.aliases = {"champion": "3"} if aliases is None else aliases
        self.filters: list[str] = []
        self.alias_calls: list[tuple[str, str, str]] = []

    def search_model_versions(self, filter_string: str):
        self.filters.append(filter_string)
        return [SimpleNamespace(version=v, run_id=r) for v, r in self.versions]

    def get_run(self, run_id: str):
        assert run_id.startswith("train-run-")
        return SimpleNamespace(data=SimpleNamespace(metrics=self.metrics, tags=self.tags))

    def get_model_version_by_alias(self, name: str, alias: str):
        if alias not in self.aliases:
            raise MlflowException(f"alias {alias} not found")
        return SimpleNamespace(version=self.aliases[alias])

    def set_registered_model_alias(self, name: str, alias: str, version: str) -> None:
        self.alias_calls.append((name, alias, version))
        self.aliases[alias] = version


def test_reads_challenger_and_champion_metrics_of_the_run():
    client = FakeMlflowClient()
    evaluation = MlflowMetricsReader(client, "fraud-xgb").read(RUN_ID)

    assert client.filters == [f"name='fraud-xgb' and tag.run_id='{RUN_ID}'"]
    assert evaluation == {
        "challenger": {
            "version": "4",
            "pr_auc": 0.83,
            "recall_at_p90": 0.68,
            "p95_latency_ms": 6.4,
        },
        "champion": {"version": "3", "pr_auc": 0.71, "recall_at_p90": 0.52, "p95_latency_ms": 6.1},
        "gate_passed": True,
        "gate_reasons": "beats champion",
    }


def test_latest_version_wins_and_gate_tag_is_parsed():
    client = FakeMlflowClient(
        versions=[("9", "train-run-9"), ("10", "train-run-10")], tags={"gate_passed": "false"}
    )
    evaluation = MlflowMetricsReader(client, "fraud-xgb").read(RUN_ID)
    assert evaluation["challenger"]["version"] == "10"
    assert evaluation["gate_passed"] is False


def test_first_model_has_no_champion():
    metrics = {"pr_auc": 0.8, "recall_at_p90": 0.6, "p95_latency_ms": 5.0}
    client = FakeMlflowClient(metrics=metrics, tags={"gate_reasons": ""}, aliases={})
    evaluation = MlflowMetricsReader(client, "fraud-xgb").read(RUN_ID)
    assert evaluation["champion"] is None


def test_missing_challenger_is_an_error():
    with pytest.raises(ChallengerNotFound):
        MlflowMetricsReader(FakeMlflowClient(versions=[]), "fraud-xgb").read(RUN_ID)


def test_move_champion_returns_the_previous_version():
    client = FakeMlflowClient()
    assert MlflowAliasMover(client, "fraud-xgb").move_champion("4") == "3"
    assert client.alias_calls == [("fraud-xgb", "champion", "4")]
    assert MlflowAliasMover(FakeMlflowClient(aliases={}), "fraud-xgb").move_champion("1") is None
