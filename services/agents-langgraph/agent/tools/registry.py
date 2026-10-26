"""read_mlflow_metrics and move_alias, following docs/architecture/retrain-contract.md."""

from typing import Any, Protocol

from mlflow.exceptions import MlflowException

from agent.state import ModelMetrics
from agent.tools import Evaluation

CHAMPION = "champion"


class RegistryClient(Protocol):
    def search_model_versions(self, filter_string: str) -> list[Any]: ...

    def get_run(self, run_id: str) -> Any: ...

    def get_model_version_by_alias(self, name: str, alias: str) -> Any: ...

    def set_registered_model_alias(self, name: str, alias: str, version: str) -> None: ...


class ChallengerNotFound(LookupError):
    pass


def alias_version(client: RegistryClient, model_name: str, alias: str) -> str | None:
    try:
        return str(client.get_model_version_by_alias(model_name, alias).version)
    except MlflowException:
        return None


def model_metrics(version: str | None, metrics: dict, prefix: str) -> ModelMetrics:
    return {
        "version": version,
        "pr_auc": metrics.get(f"{prefix}pr_auc"),
        "recall_at_p90": metrics.get(f"{prefix}recall_at_p90"),
        "p95_latency_ms": metrics.get(f"{prefix}p95_latency_ms"),
    }


class MlflowMetricsReader:
    def __init__(self, client: RegistryClient, model_name: str) -> None:
        self._client = client
        self._model_name = model_name

    def read(self, run_id: str) -> Evaluation:
        versions = self._client.search_model_versions(
            f"name='{self._model_name}' and tag.run_id='{run_id}'"
        )
        if not versions:
            raise ChallengerNotFound(f"no {self._model_name} version tagged run_id={run_id}")
        version = max(versions, key=lambda v: int(v.version))
        run = self._client.get_run(version.run_id)
        metrics, tags = run.data.metrics, run.data.tags

        challenger = model_metrics(str(version.version), metrics, prefix="")
        champion_version = alias_version(self._client, self._model_name, CHAMPION)
        champion = model_metrics(champion_version, metrics, prefix="champion_")
        has_champion = champion_version is not None or champion["pr_auc"] is not None

        return {
            "challenger": challenger,
            "champion": champion if has_champion else None,
            "gate_passed": tags.get("gate_passed") == "true",
            "gate_reasons": tags.get("gate_reasons", ""),
        }


class MlflowAliasMover:
    """move_alias: the only registry write the agent can make is pointing @champion."""

    def __init__(self, client: RegistryClient, model_name: str) -> None:
        self._client = client
        self._model_name = model_name

    def move_champion(self, version: str) -> str | None:
        previous = alias_version(self._client, self._model_name, CHAMPION)
        self._client.set_registered_model_alias(self._model_name, CHAMPION, str(version))
        return previous
