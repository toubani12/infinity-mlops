import asyncio
import threading
import uuid

from agent.graph import thread
from agent.runs import run_id_for
from tests.conftest import make_harness
from tests.fakes import FakeRetrainLauncher


def another_report(drift_report: dict) -> dict:
    return drift_report | {"report_id": str(uuid.uuid4())}


async def until(condition, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        assert asyncio.get_running_loop().time() < deadline, "condition not reached"
        await asyncio.sleep(0.01)


async def test_alert_during_a_retrain_is_attached_to_the_active_run(drift_report):
    release = threading.Event()
    harness = make_harness(launcher=FakeRetrainLauncher(release=release))
    manager = harness.manager()

    run_id = await manager.on_drift_detected(drift_report)
    await until(lambda: "retrain_started" in harness.publisher.steps())
    late = another_report(drift_report)
    attached_to = await manager.on_drift_detected(late)
    release.set()
    await manager.wait_idle()

    assert attached_to == run_id
    assert harness.launcher.launched == [run_id]
    assert harness.publisher.steps(run_id_for(late["report_id"])) == []
    attached = [e for e in harness.publisher.on("agent.events") if e["payload"].get("attached")]
    assert [e["payload"]["report_id"] for e in attached] == [late["report_id"]]
    state = await manager._graph.aget_state(thread(run_id))
    assert state.values["attached_reports"] == [late["report_id"]]
    assert manager.list_runs()[0]["attached_reports"] == [late["report_id"]]
    harness.assert_events_match_contract()


async def test_run_waiting_for_approval_still_blocks_a_new_retrain(harness, drift_report):
    manager = harness.manager()
    run_id = await manager.on_drift_detected(drift_report)
    await manager.wait_idle()
    late = another_report(drift_report)

    assert await manager.on_drift_detected(late) == run_id
    assert await manager.on_drift_detected(late) == run_id

    assert manager.active_run_id == run_id
    assert manager.list_runs()[0]["status"] == "awaiting_approval"
    assert harness.launcher.launched == [run_id]
    state = await manager._graph.aget_state(thread(run_id))
    assert state.values["attached_reports"] == [late["report_id"]]
    assert sum(1 for e in harness.publisher.on("agent.events") if e["payload"].get("attached")) == 1


async def test_finished_run_frees_the_slot_for_the_next_alert(harness, drift_report):
    manager = harness.manager()
    noise = {"drift_share": 0.1, "metrics": {"pr_auc": 0.84, "reference_pr_auc": 0.84}}
    first = await manager.on_drift_detected(drift_report | noise)
    await manager.wait_idle()
    second = await manager.on_drift_detected(another_report(drift_report))
    await manager.wait_idle()

    assert first != second
    newest, oldest = manager.list_runs()
    assert (oldest["run_id"], oldest["status"], oldest["outcome"]) == (first, "finished", "noise")
    assert (newest["run_id"], newest["status"]) == (second, "awaiting_approval")
    assert manager.active_run_id == second


async def test_redelivered_alert_does_not_start_a_second_run(harness, drift_report):
    manager = harness.manager()
    noise = {"drift_share": 0.1, "metrics": {"pr_auc": 0.84, "reference_pr_auc": 0.84}}
    await manager.on_drift_detected(drift_report | noise)
    await manager.wait_idle()

    restarted = harness.manager()
    assert await restarted.on_drift_detected(drift_report | noise) is None
    assert harness.publisher.steps().count("received") == 1


async def test_invalid_alert_is_ignored(harness, drift_report):
    manager = harness.manager()
    assert await manager.on_drift_detected({"report_id": "x"}) is None
    assert harness.publisher.sent == []


async def test_tool_error_publishes_failed_and_frees_the_slot(drift_report):
    class BrokenLauncher(FakeRetrainLauncher):
        def launch(self, run_id: str) -> str:
            raise RuntimeError("forbidden: jobs.batch")

    harness = make_harness(launcher=BrokenLauncher())
    manager = harness.manager()
    run_id = await manager.on_drift_detected(drift_report)
    await manager.wait_idle()

    assert harness.publisher.steps(run_id) == ["received", "qualified", "failed"]
    assert (
        harness.publisher.on("agent.events")[-1]["message"] == "RuntimeError: forbidden: jobs.batch"
    )
    assert manager.active_run_id is None
    assert manager.list_runs()[0]["outcome"] == "failed"
    harness.assert_events_match_contract()
