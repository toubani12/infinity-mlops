import os
import uuid

import psycopg
import pytest

from agent.main import open_checkpointer
from agent.runs import RunManager
from tests.conftest import make_harness
from tests.test_approval import command

DATABASE_URL = os.environ.get("AGENT_TEST_DATABASE_URL", "")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not DATABASE_URL, reason="AGENT_TEST_DATABASE_URL is not set"),
]


@pytest.fixture(autouse=True)
async def empty_checkpoints():
    async with open_checkpointer(DATABASE_URL):
        pass
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("truncate checkpoints, checkpoint_blobs, checkpoint_writes")


async def test_waiting_run_survives_a_restart_in_postgres(drift_report):
    report = drift_report | {"report_id": str(uuid.uuid4())}
    harness = make_harness()

    async with open_checkpointer(DATABASE_URL) as checkpointer:
        harness.checkpointer = checkpointer
        manager = harness.manager()
        run_id = await manager.on_drift_detected(report)
        await manager.wait_idle()
        assert manager.list_runs()[0]["status"] == "awaiting_approval"

    async with open_checkpointer(DATABASE_URL) as checkpointer:
        harness.checkpointer = checkpointer
        restarted = RunManager(harness.graph(), harness.deps)
        await restarted.recover()
        assert restarted.active_run_id == run_id
        assert await restarted.on_command(command(run_id))
        await restarted.wait_idle()

    assert harness.aliases.moves == ["4"]
    assert harness.publisher.steps(run_id)[-3:] == ["approved", "promoted", "completed"]
    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(
            "select count(*) from checkpoints where thread_id = %s", (run_id,)
        ).fetchone()
    assert rows[0] > 0
