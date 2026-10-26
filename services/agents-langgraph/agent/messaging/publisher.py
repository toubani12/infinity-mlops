import json
from typing import Protocol

from aiokafka import AIOKafkaProducer


class Publisher(Protocol):
    async def send(self, topic: str, key: str, value: dict) -> None: ...


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            key_serializer=lambda key: key.encode(),
            value_serializer=lambda value: json.dumps(value).encode(),
            acks="all",
            enable_idempotence=True,
        )
        try:
            await producer.start()
        except Exception:
            await producer.stop()
            raise
        self._producer = producer

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()

    async def send(self, topic: str, key: str, value: dict) -> None:
        if self._producer is None:
            raise RuntimeError("kafka producer is not connected")
        await self._producer.send_and_wait(topic, value=value, key=key)
