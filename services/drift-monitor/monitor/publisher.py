import asyncio
import json
from datetime import UTC, datetime
from typing import Protocol

from monitor.report import DriftResult, iso

TOPIC = "drift.detected"


class Publisher(Protocol):
    def publish(self, event: dict) -> None: ...


def build_event(result: DriftResult, detected_at: datetime | None = None) -> dict:
    signals = result.signals
    event = {
        "report_id": result.report_id,
        "detected_at": iso(detected_at or datetime.now(UTC)),
        "window": {
            "start": iso(result.window.start),
            "end": iso(result.window.end),
            "rows": result.rows,
        },
        "drift_share": round(signals.drift_share, 4),
        "drifted_features": signals.drifted_features,
        "missing_features": signals.missing_features,
        "out_of_range_share": round(signals.out_of_range_share, 4),
        "metrics": {
            "pr_auc": signals.pr_auc,
            "reference_pr_auc": signals.reference_pr_auc,
            "recall_at_p90": result.recall_at_p90,
            "labeled_rows": result.labeled_rows,
        },
    }
    if result.model_version is not None:
        event["model_version"] = result.model_version
    if result.report_uri is not None:
        event["report_uri"] = result.report_uri
    return event


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str, topic: str = TOPIC) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic

    def publish(self, event: dict) -> None:
        asyncio.run(self._send(event))

    async def _send(self, event: dict) -> None:
        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers, acks="all")
        await producer.start()
        try:
            await producer.send_and_wait(
                self._topic, json.dumps(event).encode(), key=event["report_id"].encode()
            )
        finally:
            await producer.stop()
