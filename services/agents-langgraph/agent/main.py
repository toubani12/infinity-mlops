import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Response
from langgraph.checkpoint.memory import InMemorySaver
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from agent.config import Settings
from agent.deps import AgentDeps
from agent.events import EventEmitter
from agent.graph import build_graph
from agent.llm import build_explainer
from agent.messaging.consumer import consume_forever
from agent.messaging.publisher import KafkaPublisher
from agent.runs import RunManager
from agent.tools import Toolset
from agent.wiring import build_toolset

log = logging.getLogger("agent")

ToolsetFactory = Callable[[Settings, EventEmitter], Toolset]


async def connect_and_consume(app: FastAPI, settings: Settings, publisher: KafkaPublisher) -> None:
    while True:
        try:
            await publisher.start()
            break
        except Exception as exc:
            log.warning("kafka producer not ready: %s, retrying", exc)
            await asyncio.sleep(5)
    app.state.kafka_ready = True
    await consume_forever(
        settings.kafka_bootstrap_servers,
        settings.drift_topic,
        settings.consumer_group,
        app.state.runs.on_drift_detected,
    )


def create_app(
    settings: Settings | None = None,
    toolset_factory: ToolsetFactory = build_toolset,
    connect_kafka: bool = True,
) -> FastAPI:
    settings = settings or Settings()
    publisher = KafkaPublisher(settings.kafka_bootstrap_servers)
    emitter = EventEmitter(publisher, settings.events_topic)
    deps = AgentDeps(
        settings=settings,
        tools=toolset_factory(settings, emitter),
        emitter=emitter,
        explainer=build_explainer(settings),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.kafka_ready = False
        app.state.runs = RunManager(build_graph(deps, InMemorySaver()), deps)
        task = (
            asyncio.create_task(connect_and_consume(app, settings, publisher))
            if connect_kafka
            else None
        )
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            await publisher.stop()

    app = FastAPI(title="agents-langgraph", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "kafka": "connected" if app.state.kafka_ready else "connecting",
            "active_run_id": app.state.runs.active_run_id,
        }

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/runs")
    async def runs() -> list[dict]:
        return app.state.runs.list_runs()

    return app


def run() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.http_port)


if __name__ == "__main__":
    run()
