import asyncio
import logging
import time
from typing import Any, Protocol

from aiokafka.structs import TopicPartition

from app.core.config import Settings
from app.core.metrics import KAFKA_BATCH_SIZE, KAFKA_MESSAGES
from app.inference.service import InferenceService, ModelUnavailableError, Transaction
from app.messaging.codec import InvalidMessageError, decode_raw, encode_scored

log = logging.getLogger(__name__)


class Consumer(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def getmany(self, *, timeout_ms: int, max_records: int) -> dict[Any, list[Any]]: ...
    async def commit(self) -> None: ...
    def seek(self, partition: TopicPartition, offset: int) -> None: ...


class Producer(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, topic: str, value: bytes, key: bytes) -> asyncio.Future: ...


class ScoringConsumer:
    """At-least-once: offsets are committed only after every scored message of the batch is
    acknowledged by the broker."""

    def __init__(
        self,
        consumer: Consumer,
        producer: Producer,
        service: InferenceService,
        *,
        output_topic: str,
        batch_size: int = 64,
        max_wait_ms: int = 50,
        idle_seconds: float = 1.0,
    ) -> None:
        self._consumer = consumer
        self._producer = producer
        self._service = service
        self._output_topic = output_topic
        self._batch_size = batch_size
        self._max_wait_ms = max_wait_ms
        self._idle_seconds = idle_seconds
        self._stopping = asyncio.Event()

    async def collect(self) -> list[Any]:
        records: list[Any] = []
        deadline = time.monotonic() + self._max_wait_ms / 1000
        while len(records) < self._batch_size and not self._stopping.is_set():
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            fetched = await self._consumer.getmany(
                timeout_ms=remaining, max_records=self._batch_size - len(records)
            )
            records.extend(record for batch in fetched.values() for record in batch)
            if remaining == 0:
                break
        return records

    def decode(self, records: list[Any]) -> list[Transaction]:
        transactions = []
        for record in records:
            try:
                transactions.append(decode_raw(record.value))
            except InvalidMessageError as error:
                KAFKA_MESSAGES.labels("invalid").inc()
                log.warning(
                    "skipping poison message at partition %s offset %s: %s",
                    record.partition,
                    record.offset,
                    error,
                )
        return transactions

    async def process(self, records: list[Any]) -> int:
        transactions = self.decode(records)
        if transactions:
            scores = await asyncio.to_thread(self._service.score, transactions, "kafka")
            deliveries = [
                await self._producer.send(
                    self._output_topic, encode_scored(score), key=score.transaction_id.encode()
                )
                for score in scores
            ]
            await asyncio.gather(*deliveries)
            KAFKA_MESSAGES.labels("scored").inc(len(scores))
            KAFKA_BATCH_SIZE.observe(len(scores))
        await self._consumer.commit()
        return len(transactions)

    async def run(self) -> None:
        while not self._stopping.is_set():
            if self._service.model is None:
                await asyncio.sleep(self._idle_seconds)
                continue
            records = await self.collect()
            if not records:
                continue
            try:
                await self.process(records)
            except ModelUnavailableError:
                log.warning("model unavailable, rewinding the batch")
                self.rewind(records)
                await asyncio.sleep(self._idle_seconds)
            except Exception:
                log.exception("scoring batch failed, rewinding it")
                self.rewind(records)
                await asyncio.sleep(self._idle_seconds)

    def rewind(self, records: list[Any]) -> None:
        first: dict[TopicPartition, int] = {}
        for record in records:
            partition = TopicPartition(record.topic, record.partition)
            first[partition] = min(first.get(partition, record.offset), record.offset)
        for partition, offset in first.items():
            self._consumer.seek(partition, offset)

    def stop(self) -> None:
        self._stopping.set()


class KafkaScoring:
    def __init__(self, settings: Settings, service: InferenceService) -> None:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

        self._consumer = AIOKafkaConsumer(
            settings.kafka_input_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers, linger_ms=5, acks="all"
        )
        self.scoring = ScoringConsumer(
            self._consumer,
            self._producer,
            service,
            output_topic=settings.kafka_output_topic,
            batch_size=settings.kafka_batch_size,
            max_wait_ms=settings.kafka_max_wait_ms,
        )
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        await self._producer.start()
        await self._consumer.start()
        self._task = asyncio.create_task(self.scoring.run())

    async def stop(self) -> None:
        self.scoring.stop()
        if self._task:
            await self._task
        await self._consumer.stop()
        await self._producer.stop()
