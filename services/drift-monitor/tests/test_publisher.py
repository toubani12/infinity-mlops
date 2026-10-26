import json

from jsonschema import Draft202012Validator, FormatChecker

from monitor.publisher import KafkaPublisher, build_event
from monitor.report import Window, analyze
from monitor.thresholds import Thresholds
from tests.conftest import CONTRACTS, NOW, frame

SCHEMA = json.loads((CONTRACTS / "events" / "drift.detected.v1.json").read_text())


def test_event_matches_contract() -> None:
    result = analyze(
        frame(2000, seed=1, shift={"v14": 2.0}),
        frame(2000),
        Window.last_hours(NOW, 1),
        Thresholds(),
    )
    event = build_event(result, NOW)
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(event)
    assert event["detected_at"] == "2026-10-26T10:20:00Z"
    assert event["window"] == {
        "start": "2026-10-26T10:00:00Z",
        "end": "2026-10-26T10:20:00Z",
        "rows": 2000,
    }
    assert "v14" in event["drifted_features"]
    assert event["model_version"] == "3"


def test_kafka_publisher_sends_keyed_event(monkeypatch) -> None:
    import aiokafka

    sent = []

    class Producer:
        def __init__(self, **options) -> None:
            self.options = options

        async def start(self) -> None:
            sent.append("start")

        async def send_and_wait(self, topic, value, key) -> None:
            sent.append((topic, json.loads(value), key))

        async def stop(self) -> None:
            sent.append("stop")

    monkeypatch.setattr(aiokafka, "AIOKafkaProducer", Producer)
    KafkaPublisher("kafka:29092").publish({"report_id": "r-1", "drift_share": 0.4})
    assert sent == [
        "start",
        ("drift.detected", {"report_id": "r-1", "drift_share": 0.4}, b"r-1"),
        "stop",
    ]
