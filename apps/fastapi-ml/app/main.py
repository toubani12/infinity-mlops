import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.metrics import REQUEST_LATENCY
from app.inference.model import MlflowModelLoader, ModelLoader
from app.inference.prediction_log import PredictionLogWriter, store_from_uri
from app.inference.service import InferenceService, ModelUnavailableError
from app.messaging.consumer import KafkaScoring
from app.messaging.model_events import kafka_model_events

log = logging.getLogger(__name__)


async def load_until_ready(service: InferenceService, interval: float) -> None:
    while service.model is None:
        await asyncio.sleep(interval)
        with contextlib.suppress(ModelUnavailableError):
            await service.reload()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    service: InferenceService = app.state.service
    retry: asyncio.Task | None = None
    try:
        await service.reload()
    except ModelUnavailableError:
        log.warning("starting without a model, /predict answers 503 until a load succeeds")
        retry = asyncio.create_task(
            load_until_ready(service, app.state.settings.model_retry_seconds)
        )
    kafka = (
        app.state.kafka_factory(app.state.settings, service)
        if app.state.settings.kafka_enabled
        else None
    )
    writer: PredictionLogWriter | None = app.state.prediction_log
    flusher = asyncio.create_task(writer.run()) if writer else None
    model_events = (
        app.state.model_events_factory(app.state.settings, service)
        if app.state.settings.model_events_enabled
        else None
    )
    if model_events:
        await model_events.start()
    if kafka:
        await kafka.start()
    yield
    if kafka:
        await kafka.stop()
    if model_events:
        await model_events.stop()
    if flusher and writer:
        flusher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await flusher
        await asyncio.to_thread(writer.flush)
    if retry:
        retry.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await retry


def build_prediction_log(settings: Settings) -> PredictionLogWriter | None:
    if not settings.prediction_log_enabled:
        return None
    return PredictionLogWriter(
        store_from_uri(settings.prediction_log_uri, settings.s3_endpoint_url),
        max_rows=settings.prediction_log_max_rows,
        max_seconds=settings.prediction_log_max_seconds,
    )


def create_app(
    settings: Settings | None = None,
    loader: ModelLoader | None = None,
    kafka_factory: Callable[[Settings, InferenceService], Any] = KafkaScoring,
    prediction_log: PredictionLogWriter | None = None,
    model_events_factory: Callable[[Settings, InferenceService], Any] = kafka_model_events,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = settings or get_settings()
    app = FastAPI(title="fastapi-ml inference", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.kafka_factory = kafka_factory
    app.state.model_events_factory = model_events_factory
    app.state.prediction_log = prediction_log or build_prediction_log(settings)
    app.state.service = InferenceService(
        loader or MlflowModelLoader(settings.mlflow_tracking_uri),
        settings.model_name,
        settings.model_alias,
        settings.fraud_threshold,
        sink=app.state.prediction_log.add if app.state.prediction_log else None,
    )
    app.include_router(router)

    @app.middleware("http")
    async def observe_latency(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        if request.url.path != "/metrics":
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            REQUEST_LATENCY.labels(request.method, path, str(response.status_code)).observe(
                time.perf_counter() - started
            )
        return response

    return app
