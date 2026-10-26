import asyncio
import io
import logging
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from app.core.metrics import PREDICTION_LOG_ROWS
from app.inference.model import FEATURES
from app.inference.service import Score, Transaction

log = logging.getLogger(__name__)

COLUMNS = [
    "transaction_id",
    "timestamp",
    *FEATURES,
    "fraud_score",
    "is_fraud",
    "model_version",
    "latency_ms",
    "label",
]


class PredictionStore(Protocol):
    def write(self, key: str, data: bytes) -> str: ...


class LocalPredictionStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def write(self, key: str, data: bytes) -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)


class S3PredictionStore:
    def __init__(self, bucket: str, prefix: str = "", client: Any = None) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._client = client

    def write(self, key: str, data: bytes) -> str:
        if self._client is None:
            import boto3

            self._client = boto3.client("s3")
        full_key = f"{self._prefix}/{key}" if self._prefix else key
        self._client.put_object(Bucket=self._bucket, Key=full_key, Body=data)
        return f"s3://{self._bucket}/{full_key}"


def store_from_uri(uri: str, endpoint_url: str | None = None) -> PredictionStore:
    if not uri.startswith("s3://"):
        return LocalPredictionStore(uri.removeprefix("file://"))
    bucket, _, prefix = uri.removeprefix("s3://").partition("/")
    import boto3

    return S3PredictionStore(bucket, prefix, boto3.client("s3", endpoint_url=endpoint_url))


def partition_key(scored_at: datetime) -> str:
    return f"dt={scored_at:%Y-%m-%d}/hour={scored_at:%H}/part-{uuid.uuid4()}.parquet"


class PredictionLogWriter:
    """Buffers scored rows and writes one parquet file per scoring hour, when the buffer reaches
    `max_rows` or its oldest row is `max_seconds` old. Rows are partitioned by scoring time so
    a replay of old transactions still lands in the window drift-monitor reads."""

    def __init__(
        self,
        store: PredictionStore,
        *,
        max_rows: int = 1000,
        max_seconds: float = 60.0,
        max_buffered: int = 50_000,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self.max_rows = max_rows
        self.max_seconds = max_seconds
        self._max_buffered = max_buffered
        self._clock = clock
        self._rows: list[tuple[datetime, dict[str, Any]]] = []
        self._oldest: float | None = None
        self._lock = threading.Lock()

    def add(self, transactions: list[Transaction], scores: list[Score]) -> None:
        scored_at = self._clock()
        rows = [
            (scored_at, self._row(transaction, score))
            for transaction, score in zip(transactions, scores, strict=True)
        ]
        with self._lock:
            self._rows.extend(rows)
            self._oldest = self._oldest or time.monotonic()
            overflow = len(self._rows) - self._max_buffered
            if overflow > 0:
                del self._rows[:overflow]
                PREDICTION_LOG_ROWS.labels("dropped").inc(overflow)

    @staticmethod
    def _row(transaction: Transaction, score: Score) -> dict[str, Any]:
        return {
            "transaction_id": transaction.transaction_id,
            "timestamp": transaction.timestamp,
            **transaction.features,
            "fraud_score": score.fraud_score,
            "is_fraud": score.is_fraud,
            "model_version": score.model_version,
            "latency_ms": score.latency_ms,
            "label": transaction.label,
        }

    @property
    def buffered(self) -> int:
        return len(self._rows)

    def due(self) -> bool:
        with self._lock:
            if not self._rows:
                return False
            age = time.monotonic() - (self._oldest or time.monotonic())
            return len(self._rows) >= self.max_rows or age >= self.max_seconds

    def flush(self) -> list[str]:
        with self._lock:
            rows, self._rows, self._oldest = self._rows, [], None
        written: list[str] = []
        by_hour: dict[str, list[tuple[datetime, dict[str, Any]]]] = {}
        for scored_at, row in rows:
            by_hour.setdefault(f"{scored_at:%Y-%m-%d %H}", []).append((scored_at, row))
        for group in by_hour.values():
            try:
                written.append(self._store.write(partition_key(group[0][0]), to_parquet(group)))
                PREDICTION_LOG_ROWS.labels("written").inc(len(group))
            except Exception:
                log.exception("prediction log write failed, keeping %d rows", len(group))
                with self._lock:
                    self._rows[:0] = group
                    self._oldest = self._oldest or time.monotonic()
        return written

    async def run(self, interval: float = 1.0) -> None:
        while True:
            await asyncio.sleep(interval)
            if self.due():
                await asyncio.to_thread(self.flush)


def to_parquet(group: list[tuple[datetime, dict[str, Any]]]) -> bytes:
    frame = pd.DataFrame([row for _, row in group], columns=COLUMNS)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["label"] = frame["label"].astype("Int64")
    frame["is_fraud"] = frame["is_fraud"].astype(bool)
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    return buffer.getvalue()
