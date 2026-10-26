from fastapi.testclient import TestClient

from agent.config import Settings
from agent.main import create_app
from agent.messaging.consumer import decode, dispatch


def test_health_metrics_and_runs_endpoints():
    with TestClient(create_app(Settings(_env_file=None), connect_kafka=False)) as client:
        health = client.get("/health").json()
        assert health == {"status": "ok", "kafka": "connecting", "active_run_id": None}
        assert "agent_runs_started_total" in client.get("/metrics").text
        assert client.get("/runs").json() == []


def test_decode_accepts_only_json_objects():
    assert decode(b'{"a": 1}') == {"a": 1}
    assert decode(b"[1]") is None
    assert decode(b"not json") is None
    assert decode(None) is None


async def test_dispatch_isolates_handler_errors():
    seen = []

    async def handler(message: dict) -> None:
        seen.append(message)
        raise ValueError("boom")

    await dispatch(b'{"a": 1}', handler, "drift.detected")
    await dispatch(b"garbage", handler, "drift.detected")
    assert seen == [{"a": 1}]
