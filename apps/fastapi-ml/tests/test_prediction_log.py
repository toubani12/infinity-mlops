import asyncio
import io
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.inference.model import FEATURES
from app.inference.prediction_log import (
    COLUMNS,
    LocalPredictionStore,
    PredictionLogWriter,
    S3PredictionStore,
    store_from_uri,
)
from app.inference.service import Score, Transaction
from app.main import build_prediction_log, create_app
from tests.conftest import StaticLoader, transaction_payload

NOW = datetime(2026, 10, 26, 9, 59, 30, tzinfo=UTC)


def scored(label: int | None = None) -> tuple[Transaction, Score]:
    transaction = Transaction("t-1", NOW, {name: 0.5 for name in FEATURES}, label)
    score = Score("t-1", NOW, 0.75, True, 0.5, "fraud-xgb", "4", 2.0)
    return transaction, score


def add(writer: PredictionLogWriter, count: int, label: int | None = None) -> None:
    pairs = [scored(label) for _ in range(count)]
    writer.add([t for t, _ in pairs], [s for _, s in pairs])


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body


class FlakyStore(LocalPredictionStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.failures = 1

    def write(self, key: str, data: bytes) -> str:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("minio down")
        return super().write(key, data)


def test_flush_writes_hourly_partitioned_parquet(tmp_path) -> None:
    writer = PredictionLogWriter(LocalPredictionStore(tmp_path), clock=lambda: NOW)
    add(writer, 2, label=1)
    add(writer, 1)
    (path,) = writer.flush()
    relative = Path(path).relative_to(tmp_path)
    assert relative.parts[:2] == ("dt=2026-10-26", "hour=09")
    assert relative.name.startswith("part-") and relative.suffix == ".parquet"
    frame = pd.read_parquet(path)
    assert list(frame.columns) == COLUMNS
    assert frame["label"].tolist()[:2] == [1, 1] and pd.isna(frame["label"].iloc[2])
    assert str(frame["timestamp"].dt.tz) == "UTC"
    assert frame["model_version"].unique().tolist() == ["4"]
    assert writer.buffered == 0 and writer.flush() == []


def test_rows_scored_in_different_hours_go_to_different_partitions(tmp_path) -> None:
    times = iter([NOW, NOW + timedelta(minutes=1)])
    writer = PredictionLogWriter(LocalPredictionStore(tmp_path), clock=lambda: next(times))
    add(writer, 1)
    add(writer, 1)
    hours = sorted(Path(p).parent.name for p in writer.flush())
    assert hours == ["hour=09", "hour=10"]


def test_due_by_count_and_by_age(tmp_path) -> None:
    writer = PredictionLogWriter(LocalPredictionStore(tmp_path), max_rows=3, max_seconds=3600)
    assert not writer.due()
    add(writer, 2)
    assert not writer.due()
    add(writer, 1)
    assert writer.due()
    aged = PredictionLogWriter(LocalPredictionStore(tmp_path), max_seconds=0.0001)
    add(aged, 1)
    time.sleep(0.01)
    assert aged.due()


def test_failed_write_keeps_rows_for_the_next_flush(tmp_path) -> None:
    writer = PredictionLogWriter(FlakyStore(tmp_path), clock=lambda: NOW)
    add(writer, 2)
    assert writer.flush() == []
    assert writer.buffered == 2
    (path,) = writer.flush()
    assert len(pd.read_parquet(path)) == 2


def test_buffer_is_bounded(tmp_path) -> None:
    writer = PredictionLogWriter(LocalPredictionStore(tmp_path), max_buffered=5)
    add(writer, 8)
    assert writer.buffered == 5


def test_s3_store_writes_under_bucket_and_prefix() -> None:
    client = FakeS3()
    uri = S3PredictionStore("predictions", "/live/", client).write("dt=x/part.parquet", b"data")
    assert uri == "s3://predictions/live/dt=x/part.parquet"
    assert client.objects == {("predictions", "live/dt=x/part.parquet"): b"data"}
    writer = PredictionLogWriter(S3PredictionStore("predictions", client=client))
    add(writer, 1)
    (written,) = writer.flush()
    key = written.removeprefix("s3://predictions/")
    assert len(pd.read_parquet(io.BytesIO(client.objects[("predictions", key)]))) == 1


def test_store_from_uri(tmp_path) -> None:
    assert isinstance(store_from_uri(str(tmp_path)), LocalPredictionStore)
    assert isinstance(store_from_uri(f"file://{tmp_path}"), LocalPredictionStore)
    assert isinstance(store_from_uri("s3://predictions", "http://minio:9000"), S3PredictionStore)


def test_periodic_flush(tmp_path) -> None:
    async def scenario() -> list[Path]:
        writer = PredictionLogWriter(LocalPredictionStore(tmp_path), max_rows=1)
        task = asyncio.create_task(writer.run(interval=0.01))
        add(writer, 1)
        async with asyncio.timeout(5):
            while not list(tmp_path.rglob("*.parquet")):
                await asyncio.sleep(0.01)
        task.cancel()
        assert writer.buffered == 0
        return list(tmp_path.rglob("*.parquet"))

    assert len(asyncio.run(scenario())) == 1


def test_build_from_settings(tmp_path) -> None:
    assert build_prediction_log(Settings(prediction_log_enabled=False)) is None
    settings = Settings(prediction_log_enabled=True, prediction_log_uri=str(tmp_path))
    assert isinstance(build_prediction_log(settings), PredictionLogWriter)


def test_api_predictions_are_logged_on_shutdown(tmp_path, settings, predictor) -> None:
    requests = 3
    writer = PredictionLogWriter(LocalPredictionStore(tmp_path))
    app = create_app(settings, StaticLoader(predictor), prediction_log=writer)
    with TestClient(app) as client:
        ids = [client.post("/predict", json=transaction_payload()).json() for _ in range(requests)]
    (path,) = tmp_path.rglob("*.parquet")
    frame = pd.read_parquet(path)
    assert sorted(frame["transaction_id"]) == sorted(r["transaction_id"] for r in ids)
    assert frame["amount"].tolist() == [42.5] * requests
