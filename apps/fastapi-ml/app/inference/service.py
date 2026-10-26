import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.core.metrics import FRAUD_SCORE, MODEL_RELOADS, PREDICTIONS
from app.inference.model import FEATURES, LoadedModel, ModelLoader

log = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    timestamp: datetime
    features: dict[str, float]
    label: int | None = None


@dataclass(frozen=True)
class Score:
    transaction_id: str
    timestamp: datetime
    fraud_score: float
    is_fraud: bool
    threshold: float
    model_name: str
    model_version: str
    latency_ms: float


class InferenceService:
    def __init__(self, loader: ModelLoader, name: str, alias: str, threshold: float) -> None:
        self._loader = loader
        self._name = name
        self._alias = alias
        self.threshold = threshold
        self._model: LoadedModel | None = None
        self._reload_lock = asyncio.Lock()

    @property
    def model(self) -> LoadedModel | None:
        return self._model

    async def reload(self) -> LoadedModel:
        """Load the aliased version next to the current one and swap only on success."""
        async with self._reload_lock:
            try:
                loaded = await asyncio.to_thread(self._loader.load, self._name, self._alias)
            except Exception as error:
                MODEL_RELOADS.labels("failure").inc()
                log.warning("model reload failed, keeping %s: %s", self.describe(), error)
                raise ModelUnavailableError(str(error)) from error
            previous, self._model = self._model, loaded
            MODEL_RELOADS.labels("success").inc()
            log.info(
                "serving %s v%s (was %s)",
                loaded.name,
                loaded.version,
                previous and previous.version,
            )
            return loaded

    def describe(self) -> str:
        return f"{self._model.name} v{self._model.version}" if self._model else "no model"

    def score(self, transactions: list[Transaction], source: str) -> list[Score]:
        model = self._model
        if model is None:
            raise ModelUnavailableError("no model loaded")
        started = time.perf_counter()
        frame = pd.DataFrame([t.features for t in transactions], columns=FEATURES)
        scores = model.predictor.predict_proba(frame)[:, 1]
        latency_ms = (time.perf_counter() - started) * 1000.0 / len(transactions)
        results = []
        for transaction, value in zip(transactions, scores, strict=True):
            fraud_score = float(value)
            is_fraud = fraud_score >= self.threshold
            FRAUD_SCORE.observe(fraud_score)
            PREDICTIONS.labels(source, "fraud" if is_fraud else "legit", model.version).inc()
            results.append(
                Score(
                    transaction_id=transaction.transaction_id,
                    timestamp=transaction.timestamp,
                    fraud_score=fraud_score,
                    is_fraud=is_fraud,
                    threshold=self.threshold,
                    model_name=model.name,
                    model_version=model.version,
                    latency_ms=latency_ms,
                )
            )
        return results
