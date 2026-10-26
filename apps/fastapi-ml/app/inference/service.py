import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from app.core.metrics import FRAUD_SCORE, MODEL_RELOADS, PREDICTIONS, SERVED_MODEL
from app.inference.model import FEATURES, LoadedModel, ModelLoader

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.5


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
    def __init__(
        self,
        loader: ModelLoader,
        name: str,
        alias: str,
        threshold: float | None,
        sink: Callable[[list["Transaction"], list["Score"]], None] | None = None,
    ) -> None:
        self._loader = loader
        self._sink = sink
        self._name = name
        self._alias = alias
        self._fixed_threshold = threshold
        self._model: LoadedModel | None = None
        self._reload_lock = asyncio.Lock()
        self.last_reload_error: str | None = None

    @property
    def model(self) -> LoadedModel | None:
        return self._model

    @property
    def threshold(self) -> float:
        if self._fixed_threshold is not None:
            return self._fixed_threshold
        if self._model is not None and self._model.threshold is not None:
            return self._model.threshold
        return DEFAULT_THRESHOLD

    async def reload(self) -> LoadedModel:
        """Load the aliased version next to the current one and swap only on success."""
        async with self._reload_lock:
            try:
                loaded = await asyncio.to_thread(self._loader.load, self._name, self._alias)
            except Exception as error:
                MODEL_RELOADS.labels("failure").inc()
                self.last_reload_error = f"{type(error).__name__}: {error}"
                log.warning("model reload failed, keeping %s: %s", self.describe(), error)
                raise ModelUnavailableError(str(error)) from error
            previous, self._model = self._model, loaded
            self.last_reload_error = None
            MODEL_RELOADS.labels("success").inc()
            if previous and previous.version != loaded.version:
                with contextlib.suppress(KeyError):
                    SERVED_MODEL.remove(previous.name, previous.version)
            SERVED_MODEL.labels(loaded.name, loaded.version).set(1)
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
        threshold = self.threshold
        started = time.perf_counter()
        frame = pd.DataFrame([t.features for t in transactions], columns=FEATURES)
        scores = model.predictor.predict_proba(frame)[:, 1]
        latency_ms = (time.perf_counter() - started) * 1000.0 / len(transactions)
        results = []
        for transaction, value in zip(transactions, scores, strict=True):
            fraud_score = float(value)
            is_fraud = fraud_score >= threshold
            FRAUD_SCORE.observe(fraud_score)
            PREDICTIONS.labels(source, "fraud" if is_fraud else "legit", model.version).inc()
            results.append(
                Score(
                    transaction_id=transaction.transaction_id,
                    timestamp=transaction.timestamp,
                    fraud_score=fraud_score,
                    is_fraud=is_fraud,
                    threshold=threshold,
                    model_name=model.name,
                    model_version=model.version,
                    latency_ms=latency_ms,
                )
            )
        if self._sink:
            self._sink(transactions, results)
        return results
