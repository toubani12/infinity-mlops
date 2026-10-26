from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import numpy as np
import pandas as pd

V_FEATURES = [f"v{i}" for i in range(1, 29)]
FEATURES = [*V_FEATURES, "amount"]


class Predictor(Protocol):
    def predict_proba(self, features: pd.DataFrame) -> np.ndarray: ...


@dataclass(frozen=True)
class LoadedModel:
    name: str
    version: str
    alias: str
    predictor: Predictor
    loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    threshold: float | None = None


class ModelLoader(Protocol):
    def load(self, name: str, alias: str) -> LoadedModel: ...


class MlflowModelLoader:
    """Resolves the alias once, then loads that exact version, so the reported version always
    matches the weights being served even if the alias moves during the download."""

    def __init__(self, tracking_uri: str) -> None:
        self._tracking_uri = tracking_uri

    def load(self, name: str, alias: str) -> LoadedModel:
        import mlflow
        import mlflow.xgboost

        mlflow.set_tracking_uri(self._tracking_uri)
        client = mlflow.MlflowClient(tracking_uri=self._tracking_uri)
        model_version = client.get_model_version_by_alias(name, alias)
        version = str(model_version.version)
        tag = (model_version.tags or {}).get("decision_threshold")
        predictor: Any = mlflow.xgboost.load_model(f"models:/{name}/{version}")
        return LoadedModel(
            name=name,
            version=version,
            alias=alias,
            predictor=predictor,
            threshold=float(tag) if tag else None,
        )
