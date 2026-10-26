import asyncio
import json
from dataclasses import dataclass

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from app.core.config import Settings
from app.inference.service import InferenceService
from app.main import create_app
from app.messaging.consumer import ScoringConsumer
from tests.conftest import CONTRACTS, StaticLoader, raw

SCORED = Draft202012Validator(
    json.loads((CONTRACTS / "events" / "transaction.scored.v1.json").read_text()),
    format_checker=FormatChecker(),
)


@dataclass
class Record:
    topic: str
    partition: int
    offset: int
    value: bytes | None


class FakeConsumer:
    def __init__(self, values: list[bytes | None]) -> None:
        self.records = [Record("transaction.raw", 0, i, v) for i, v in enumerate(values)]
        self.position = 0
        self.committed = 0

    async def getmany(self, *, timeout_ms: int, max_records: int) -> dict:
        batch = self.records[self.position : self.position + max_records]
        self.position += len(batch)
        if not batch:
            await asyncio.sleep(timeout_ms / 1000)
            return {}
        return {("transaction.raw", 0): batch}

    async def commit(self) -> None:
        self.committed = self.position

    def seek(self, partition, offset: int) -> None:
        self.position = offset


class FakeProducer:
    def __init__(self, failures: int = 0) -> None:
        self.sent: list[tuple[str, bytes, bytes]] = []
        self.failures = failures

    async def send(self, topic: str, value: bytes, key: bytes) -> asyncio.Future:
        future = asyncio.get_running_loop().create_future()
        if self.failures:
            self.failures -= 1
            future.set_exception(ConnectionError("broker down"))
        else:
            self.sent.append((topic, value, key))
            future.set_result(None)
        return future


async def loaded_service(predictor, fail: bool = False) -> InferenceService:
    loader = StaticLoader(predictor)
    service = InferenceService(loader, "fraud-xgb", "champion", 0.5)
    if not fail:
        await service.reload()
    return service


def scoring(consumer, producer, service, batch_size=64) -> ScoringConsumer:
    return ScoringConsumer(
        consumer,
        producer,
        service,
        output_topic="transaction.scored",
        batch_size=batch_size,
        max_wait_ms=5,
        idle_seconds=0.01,
    )


async def run_until(worker: ScoringConsumer, done, timeout: float = 5.0) -> None:
    task = asyncio.create_task(worker.run())
    async with asyncio.timeout(timeout):
        while not done():
            await asyncio.sleep(0.005)
    worker.stop()
    await task


def test_scores_in_batches_and_publishes_valid_events(predictor) -> None:
    async def scenario() -> tuple[FakeConsumer, FakeProducer, list[int]]:
        consumer, producer = FakeConsumer([raw() for _ in range(150)]), FakeProducer()
        worker = scoring(consumer, producer, await loaded_service(predictor))
        sizes = [len(await worker.collect()) for _ in range(3)]
        consumer.position = 0
        await run_until(worker, lambda: consumer.committed == 150)
        return consumer, producer, sizes

    consumer, producer, sizes = asyncio.run(scenario())
    assert sizes == [64, 64, 22]
    assert len(producer.sent) == 150
    for topic, value, key in producer.sent:
        event = json.loads(value)
        SCORED.validate(event)
        assert topic == "transaction.scored"
        assert key.decode() == event["transaction_id"]
        assert event["model_version"] == "1"


def test_poison_messages_are_skipped_and_committed(predictor) -> None:
    values = [raw(), b"garbage", raw(v3=None), raw(), None]

    async def scenario() -> tuple[FakeConsumer, FakeProducer]:
        consumer, producer = FakeConsumer(values), FakeProducer()
        worker = scoring(consumer, producer, await loaded_service(predictor))
        await run_until(worker, lambda: consumer.committed == len(values))
        return consumer, producer

    consumer, producer = asyncio.run(scenario())
    assert len(producer.sent) == 2


def test_waits_for_a_model_before_consuming(predictor) -> None:
    async def scenario() -> FakeConsumer:
        consumer = FakeConsumer([raw()])
        service = await loaded_service(predictor, fail=True)
        worker = scoring(consumer, FakeProducer(), service)
        task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.05)
        untouched = consumer.position
        await service.reload()
        async with asyncio.timeout(5):
            while consumer.committed < 1:
                await asyncio.sleep(0.005)
        worker.stop()
        await task
        assert untouched == 0
        return consumer

    assert asyncio.run(scenario()).committed == 1


def test_failed_delivery_rewinds_the_batch(predictor) -> None:
    async def scenario() -> tuple[FakeConsumer, FakeProducer]:
        consumer, producer = FakeConsumer([raw() for _ in range(3)]), FakeProducer(failures=1)
        worker = scoring(consumer, producer, await loaded_service(predictor))
        await run_until(worker, lambda: consumer.committed == 3)
        return consumer, producer

    consumer, producer = asyncio.run(scenario())
    delivered = {json.loads(value)["transaction_id"] for _, value, _ in producer.sent}
    assert len(delivered) == 3


class FakeKafka:
    instances: list["FakeKafka"] = []

    def __init__(self, settings: Settings, service: InferenceService) -> None:
        self.events: list[str] = []
        FakeKafka.instances.append(self)

    async def start(self) -> None:
        self.events.append("start")

    async def stop(self) -> None:
        self.events.append("stop")


def test_lifespan_starts_and_stops_kafka_only_when_enabled(predictor) -> None:
    FakeKafka.instances.clear()
    for enabled in (False, True):
        app = create_app(Settings(kafka_enabled=enabled), StaticLoader(predictor), FakeKafka)
        with TestClient(app):
            pass
    assert [k.events for k in FakeKafka.instances] == [["start", "stop"]]


def test_kafka_scoring_wires_aiokafka_clients(monkeypatch, predictor) -> None:
    import aiokafka

    from app.messaging.consumer import KafkaScoring

    created: dict[str, object] = {}

    class Client(FakeConsumer):
        def __init__(self, *topics, **options) -> None:
            super().__init__([])
            self.options, self.topics, self.state = options, topics, "new"

        async def start(self) -> None:
            self.state = "started"

        async def stop(self) -> None:
            self.state = "stopped"

    def factory(kind):
        def build(*args, **kwargs):
            created[kind] = Client(*args, **kwargs)
            return created[kind]

        return build

    monkeypatch.setattr(aiokafka, "AIOKafkaConsumer", factory("consumer"))
    monkeypatch.setattr(aiokafka, "AIOKafkaProducer", factory("producer"))

    async def scenario() -> None:
        service = await loaded_service(predictor)
        kafka = KafkaScoring(Settings(kafka_bootstrap_servers="kafka:29092"), service)
        await kafka.start()
        await asyncio.sleep(0.01)
        await kafka.stop()

    asyncio.run(scenario())
    consumer, producer = created["consumer"], created["producer"]
    assert consumer.topics == ("transaction.raw",)
    assert consumer.options["group_id"] == "fastapi-ml"
    assert consumer.options["enable_auto_commit"] is False
    assert producer.options["bootstrap_servers"] == "kafka:29092"
    assert consumer.state == producer.state == "stopped"
