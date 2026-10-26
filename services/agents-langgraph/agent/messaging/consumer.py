import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

log = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[None]]


def decode(raw: bytes | None) -> dict | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


async def consume_forever(
    bootstrap_servers: str,
    topic: str,
    group_id: str,
    handler: Handler,
    retry_seconds: float = 5.0,
) -> None:
    while True:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="earliest",
        )
        try:
            await consumer.start()
            log.info("consuming %s as %s", topic, group_id)
            async for record in consumer:
                await dispatch(record.value, handler, topic)
        except KafkaError as exc:
            log.warning("kafka unavailable for %s: %s, retrying", topic, exc)
        finally:
            await consumer.stop()
        await asyncio.sleep(retry_seconds)


async def dispatch(raw: bytes | None, handler: Handler, topic: str) -> None:
    message = decode(raw)
    if message is None:
        log.warning("skipping undecodable message on %s", topic)
        return
    try:
        await handler(message)
    except Exception:
        log.exception("handler failed for a message on %s", topic)
