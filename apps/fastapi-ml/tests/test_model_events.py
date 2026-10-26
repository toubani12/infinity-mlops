import asyncio
import json
import time
from dataclasses import dataclass

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app.core.config import Settings
from app.inference.service import InferenceService
from app.main import create_app
from app.messaging import model_events
from app.messaging.model_events import (
    ModelEventsSubscription,
    ModelPromoted,
    PromotionListener,
    reload_group_id,
)
from tests.conftest import CONTRACTS, StaticLoader

EXAMPLE = json.loads((CONTRACTS / "examples" / "model.promoted.v1.json").read_text())


def promoted(version: str, **overrides) -> bytes:
    return json.dumps(EXAMPLE | {"version": version} | overrides).encode()


@dataclass
class Record:
    value: bytes | None


class FakeEventConsumer:
    def __init__(self, values: list[bytes | None], fail_start: bool = False) -> None:
        self.pending = [Record(v) for v in values]
        self.fail_start = fail_start
        self.commits = 0
        self.stopped = False

    async def start(self) -> None:
        if self.fail_start:
            raise ConnectionError("kafka unreachable")

    async def stop(self) -> None:
        self.stopped = True

    async def getmany(self, *, timeout_ms: int) -> dict:
        if not self.pending:
            await asyncio.sleep(0.01)
            return {}
        batch, self.pending = self.pending, []
        return {("model.promoted", 0): batch}

    async def commit(self) -> None:
        self.commits += 1


def served(predictor, versions: list[str]) -> tuple[InferenceService, StaticLoader]:
    loader = StaticLoader(predictor, versions)
    service = InferenceService(loader, "fraud-xgb", "champion", 0.5)
    asyncio.run(service.reload())
    return service, loader


def listener(service: InferenceService, attempts: int = 2) -> PromotionListener:
    return PromotionListener(
        service, model_name="fraud-xgb", alias="champion", attempts=attempts, retry_seconds=0
    )


def test_group_id_is_unique_per_replica() -> None:
    assert reload_group_id("fastapi-ml-reload", "fastapi-ml-7d9f-abc12") == (
        "fastapi-ml-reload-fastapi-ml-7d9f-abc12"
    )
    assert reload_group_id("fastapi-ml-reload").startswith("fastapi-ml-reload-")


def test_contract_example_parses() -> None:
    event = ModelPromoted.model_validate(EXAMPLE)
    assert (event.version, event.previous_version, event.reason) == ("4", "3", "promotion")


def test_promotion_reloads_the_champion(predictor) -> None:
    service, _ = served(predictor, ["1", "2"])
    before = REGISTRY.get_sample_value("model_events_total", {"result": "reloaded"}) or 0
    assert asyncio.run(listener(service).handle(promoted("2"))) == "reloaded"
    assert service.model is not None and service.model.version == "2"
    assert REGISTRY.get_sample_value("model_events_total", {"result": "reloaded"}) == before + 1
    assert REGISTRY.get_sample_value(
        "served_model_info", {"model_name": "fraud-xgb", "version": "2"}
    ) == (1.0)


def test_rollback_reloads_too(predictor) -> None:
    service, _ = served(predictor, ["2", "1"])
    event = promoted("1", previous_version="2", reason="rollback")
    assert asyncio.run(listener(service).handle(event)) == "reloaded"
    assert service.model is not None and service.model.version == "1"


def test_irrelevant_and_invalid_messages_are_skipped(predictor) -> None:
    service, loader = served(predictor, ["1", "2"])
    handle = listener(service).handle
    assert asyncio.run(handle(promoted("1"))) == "skipped"
    assert asyncio.run(handle(promoted("2", model_name="other-model"))) == "skipped"
    assert asyncio.run(handle(b"{not json")) == "invalid"
    assert asyncio.run(handle(None)) == "invalid"
    assert asyncio.run(handle(promoted("2", reason="whim"))) == "invalid"
    assert loader.calls == 1


def test_failed_reload_keeps_serving_and_is_reported(predictor) -> None:
    service, loader = served(predictor, ["1", "2"])
    loader.fail = True
    assert asyncio.run(listener(service, attempts=3).handle(promoted("2"))) == "failed"
    assert loader.calls == 4
    assert service.model is not None and service.model.version == "1"
    assert service.last_reload_error == "ConnectionError: registry unreachable"

    loader.fail = False
    assert asyncio.run(listener(service).handle(promoted("2"))) == "reloaded"
    assert service.last_reload_error is None


def test_retry_succeeds_after_a_transient_failure(predictor) -> None:
    service, loader = served(predictor, ["1", "2"])

    async def scenario() -> str:
        loader.fail = True
        handled = asyncio.create_task(
            PromotionListener(
                service, model_name="fraud-xgb", alias="champion", attempts=3, retry_seconds=0.05
            ).handle(promoted("2"))
        )
        await asyncio.sleep(0.02)
        loader.fail = False
        return await handled

    assert asyncio.run(scenario()) == "reloaded"
    assert service.model is not None and service.model.version == "2"


def test_alias_moved_again_serves_what_the_alias_points_to(predictor) -> None:
    service, _ = served(predictor, ["1", "3"])
    assert asyncio.run(listener(service).handle(promoted("2"))) == "reloaded"
    assert service.model is not None and service.model.version == "3"


def test_subscription_reconnects_then_reloads_and_commits(predictor) -> None:
    service, _ = served(predictor, ["1", "2"])
    consumers = [FakeEventConsumer([], fail_start=True), FakeEventConsumer([promoted("2")])]
    created: list[FakeEventConsumer] = []

    def factory() -> FakeEventConsumer:
        created.append(consumers.pop(0) if consumers else FakeEventConsumer([]))
        return created[-1]

    async def scenario() -> None:
        subscription = ModelEventsSubscription(factory, listener(service), retry_seconds=0.01)
        await subscription.start()
        for _ in range(200):
            if service.model is not None and service.model.version == "2":
                break
            await asyncio.sleep(0.01)
        await subscription.stop()

    asyncio.run(scenario())
    assert service.model is not None and service.model.version == "2"
    assert created[0].stopped and created[1].commits == 1 and created[1].stopped


def test_lifespan_runs_the_subscription_and_model_shows_reload_errors(predictor) -> None:
    loader = StaticLoader(predictor, ["1", "2"])
    consumer = FakeEventConsumer([])

    def subscription(settings: Settings, service: InferenceService) -> ModelEventsSubscription:
        return ModelEventsSubscription(lambda: consumer, listener(service, attempts=1))

    app = create_app(Settings(model_events_enabled=True), loader, model_events_factory=subscription)
    with TestClient(app) as client:
        loader.fail = True
        consumer.pending.append(Record(promoted("2")))
        for _ in range(200):
            if client.get("/model").json()["last_reload_error"]:
                break
            time.sleep(0.01)
        info = client.get("/model").json()
        assert info["version"] == "1"
        assert info["last_reload_error"] == "ConnectionError: registry unreachable"
    assert consumer.stopped


def test_kafka_model_events_uses_a_per_replica_group(monkeypatch, predictor) -> None:
    captured: dict = {}

    class FakeAIOKafkaConsumer:
        def __init__(self, *topics, **options) -> None:
            captured.update(options, topics=topics)

    monkeypatch.setattr("aiokafka.AIOKafkaConsumer", FakeAIOKafkaConsumer)
    monkeypatch.setattr(model_events.socket, "gethostname", lambda: "fastapi-ml-abc")
    service, _ = served(predictor, ["1"])
    subscription = model_events.kafka_model_events(Settings(), service)
    subscription._consumer_factory()
    assert captured["topics"] == ("model.promoted",)
    assert captured["group_id"] == "fastapi-ml-reload-fastapi-ml-abc"
    assert captured["auto_offset_reset"] == "latest"
    assert captured["enable_auto_commit"] is False
