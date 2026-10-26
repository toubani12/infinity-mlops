import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.metrics import REQUEST_LATENCY
from app.inference.model import MlflowModelLoader, ModelLoader
from app.inference.service import InferenceService, ModelUnavailableError

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
    yield
    if retry:
        retry.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await retry


def create_app(settings: Settings | None = None, loader: ModelLoader | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = settings or get_settings()
    app = FastAPI(title="fastapi-ml inference", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.service = InferenceService(
        loader or MlflowModelLoader(settings.mlflow_tracking_uri),
        settings.model_name,
        settings.model_alias,
        settings.fraud_threshold,
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
