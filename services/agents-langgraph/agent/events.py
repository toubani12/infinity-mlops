import uuid
from datetime import UTC, datetime

from agent.messaging.publisher import Publisher
from agent.metrics import EVENTS_PUBLISHED
from agent.state import EmittedEvent


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class EventEmitter:
    def __init__(
        self, publisher: Publisher, events_topic: str, promoted_topic: str = "model.promoted"
    ) -> None:
        self._publisher = publisher
        self._events_topic = events_topic
        self._promoted_topic = promoted_topic

    async def emit(
        self,
        run_id: str,
        step: str,
        *,
        decision: str | None = None,
        message: str | None = None,
        payload: dict | None = None,
        requires_approval: bool = False,
    ) -> EmittedEvent:
        event = {
            "run_id": run_id,
            "event_id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "step": step,
            "decision": decision,
            "requires_approval": requires_approval,
            "payload": payload or {},
        }
        if message:
            event["message"] = message
        await self._publisher.send(self._events_topic, run_id, event)
        EVENTS_PUBLISHED.labels(step=step).inc()
        return {"event_id": event["event_id"], "step": step}

    async def model_promoted(
        self,
        run_id: str | None,
        model_name: str,
        version: str,
        previous_version: str | None,
        reason: str,
    ) -> dict:
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "run_id": run_id,
            "model_name": model_name,
            "version": version,
            "alias": "champion",
            "previous_version": previous_version,
            "reason": reason,
        }
        await self._publisher.send(self._promoted_topic, model_name, event)
        return event
