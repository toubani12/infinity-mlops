import asyncio
import contextlib
import logging
import socket
from collections.abc import Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import Settings
from app.core.metrics import MODEL_EVENTS
from app.inference.service import InferenceService, ModelUnavailableError

log = logging.getLogger(__name__)

Outcome = Literal["reloaded", "skipped", "invalid", "failed"]


class ModelPromoted(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    model_name: str
    version: str
    alias: str
    previous_version: str | None
    reason: Literal["promotion", "rollback"] = "promotion"


class EventConsumer(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def getmany(self, *, timeout_ms: int) -> dict[Any, list[Any]]: ...
    async def commit(self) -> None: ...


def reload_group_id(prefix: str, hostname: str | None = None) -> str:
    """One consumer group per replica: in a shared group Kafka hands each message to a single
    member, so only one replica would reload."""
    return f"{prefix}-{hostname or socket.gethostname()}"


class PromotionListener:
    def __init__(
        self,
        service: InferenceService,
        *,
        model_name: str,
        alias: str,
        attempts: int = 3,
        retry_seconds: float = 5.0,
    ) -> None:
        self._service = service
        self._model_name = model_name
        self._alias = alias
        self._attempts = attempts
        self._retry_seconds = retry_seconds

    async def handle(self, value: bytes | None) -> Outcome:
        outcome = await self._handle(value)
        MODEL_EVENTS.labels(outcome).inc()
        return outcome

    async def _handle(self, value: bytes | None) -> Outcome:
        try:
            event = ModelPromoted.model_validate_json(value or b"")
        except ValidationError as error:
            log.warning("ignoring invalid model.promoted message: %s", error)
            return "invalid"
        if event.model_name != self._model_name or event.alias != self._alias:
            return "skipped"
        served = self._service.model
        if served is not None and served.version == event.version:
            log.info("already serving %s v%s", event.model_name, event.version)
            return "skipped"

        for attempt in range(1, self._attempts + 1):
            try:
                loaded = await self._service.reload()
            except ModelUnavailableError:
                if attempt < self._attempts:
                    await asyncio.sleep(self._retry_seconds)
                continue
            if loaded.version != event.version:
                log.warning(
                    "%s for v%s, but @%s now points to v%s",
                    event.reason,
                    event.version,
                    self._alias,
                    loaded.version,
                )
            return "reloaded"
        log.error(
            "%s to v%s not applied after %d attempts, still serving %s",
            event.reason,
            event.version,
            self._attempts,
            self._service.describe(),
        )
        return "failed"


class ModelEventsSubscription:
    """Consumes model.promoted in the background. Kafka being down never blocks /predict: the
    subscription retries its connection while the current model keeps serving."""

    def __init__(
        self,
        consumer_factory: Callable[[], EventConsumer],
        listener: PromotionListener,
        retry_seconds: float = 5.0,
    ) -> None:
        self._consumer_factory = consumer_factory
        self._listener = listener
        self._retry_seconds = retry_seconds
        self._stopping = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            await self._task

    async def run(self) -> None:
        while not self._stopping.is_set():
            consumer = self._consumer_factory()
            try:
                await consumer.start()
                await self._consume(consumer)
            except Exception as error:
                log.warning("model.promoted subscription down, retrying: %s", error)
                await self._pause()
            finally:
                await self._stop_quietly(consumer)

    async def _consume(self, consumer: EventConsumer) -> None:
        while not self._stopping.is_set():
            batches = await consumer.getmany(timeout_ms=1000)
            for record in (record for batch in batches.values() for record in batch):
                await self._listener.handle(record.value)
            if batches:
                await consumer.commit()

    async def _pause(self) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), self._retry_seconds)

    @staticmethod
    async def _stop_quietly(consumer: EventConsumer) -> None:
        try:
            await consumer.stop()
        except Exception as error:
            log.debug("consumer stop failed: %s", error)


def kafka_model_events(settings: Settings, service: InferenceService) -> ModelEventsSubscription:
    from aiokafka import AIOKafkaConsumer

    group_id = reload_group_id(settings.model_events_group_prefix)

    def consumer() -> EventConsumer:
        return AIOKafkaConsumer(
            settings.model_events_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=group_id,
            enable_auto_commit=False,
            auto_offset_reset="latest",
        )

    listener = PromotionListener(
        service,
        model_name=settings.model_name,
        alias=settings.model_alias,
        attempts=settings.model_reload_attempts,
        retry_seconds=settings.model_retry_seconds,
    )
    return ModelEventsSubscription(consumer, listener, settings.model_retry_seconds)
