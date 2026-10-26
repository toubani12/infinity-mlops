import copy
import uuid

from agent.graph import thread
from agent.runs import RunManager
from tests.conftest import contract_example, make_harness, validator

APPROVAL_PATH = [
    "received",
    "qualified",
    "retrain_started",
    "retrain_finished",
    "evaluated",
    "approval_requested",
]


def command(run_id: str, action: str = "approve", reason: str | None = None) -> dict:
    message = copy.deepcopy(contract_example("agent.commands"))
    return message | {
        "run_id": run_id,
        "command_id": str(uuid.uuid4()),
        "action": action,
        "reason": reason,
    }


async def waiting_run(harness, drift_report) -> tuple[RunManager, str]:
    manager = harness.manager()
    run_id = await manager.on_drift_detected(drift_report)
    await manager.wait_idle()
    assert manager.list_runs()[0]["status"] == "awaiting_approval"
    return manager, run_id


async def test_run_pauses_on_an_interrupt_after_requesting_approval(harness, drift_report):
    manager, run_id = await waiting_run(harness, drift_report)

    snapshot = await manager._graph.aget_state(thread(run_id))
    assert snapshot.next == ("await_approval",)
    assert snapshot.interrupts[0].value["challenger"]["version"] == "4"
    assert harness.publisher.steps(run_id) == APPROVAL_PATH
    assert harness.aliases.moves == []


async def test_approve_moves_the_champion_and_publishes_model_promoted(harness, drift_report):
    manager, run_id = await waiting_run(harness, drift_report)

    assert await manager.on_command(command(run_id))
    await manager.wait_idle()

    assert harness.aliases.moves == ["4"]
    assert harness.publisher.steps(run_id) == APPROVAL_PATH + ["approved", "promoted", "completed"]
    [promoted] = harness.publisher.on("model.promoted")
    validator("model.promoted").validate(promoted)
    assert (promoted["version"], promoted["previous_version"]) == ("4", "3")
    assert (promoted["reason"], promoted["run_id"]) == ("promotion", run_id)
    approved = harness.publisher.on("agent.events")[-3]
    assert approved["payload"]["actor"] == "badr"
    assert manager.list_runs()[0]["outcome"] == "promoted"
    assert manager.active_run_id is None
    harness.assert_events_match_contract()


async def test_reject_keeps_the_champion_and_records_the_reason(harness, drift_report):
    manager, run_id = await waiting_run(harness, drift_report)

    assert await manager.on_command(command(run_id, "reject", "latency spike in staging"))
    await manager.wait_idle()

    assert harness.aliases.moves == []
    assert harness.publisher.on("model.promoted") == []
    assert harness.publisher.steps(run_id) == APPROVAL_PATH + ["rejected", "completed"]
    rejected, completed = harness.publisher.on("agent.events")[-2:]
    assert rejected["payload"]["reason"] == "latency spike in staging"
    assert rejected["decision"] == "keep_champion"
    assert completed["message"] == "champion kept after rejection: latency spike in staging"
    state = await manager._graph.aget_state(thread(run_id))
    assert state.values["approval"] == {
        "actor": "badr",
        "action": "reject",
        "reason": "latency spike in staging",
    }
    assert manager.list_runs()[0]["outcome"] == "rejected"
    harness.assert_events_match_contract()


async def test_unknown_or_finished_runs_and_invalid_commands_are_ignored(harness, drift_report):
    manager, run_id = await waiting_run(harness, drift_report)

    assert not await manager.on_command(command(str(uuid.uuid4())))
    assert not await manager.on_command(command(run_id, "reject", None))
    assert not await manager.on_command({"run_id": run_id})
    assert await manager.on_command(command(run_id))
    assert not await manager.on_command(command(run_id))
    await manager.wait_idle()
    assert not await manager.on_command(command(run_id, "reject", "too late"))

    assert harness.aliases.moves == ["4"]
    assert harness.publisher.steps(run_id).count("promoted") == 1


async def test_alert_attached_while_waiting_does_not_break_the_resume(harness, drift_report):
    manager, run_id = await waiting_run(harness, drift_report)
    late = drift_report | {"report_id": str(uuid.uuid4())}

    assert await manager.on_drift_detected(late) == run_id
    snapshot = await manager._graph.aget_state(thread(run_id))
    assert snapshot.next == ("await_approval",)
    assert await manager.on_command(command(run_id))
    await manager.wait_idle()

    state = await manager._graph.aget_state(thread(run_id))
    assert state.values["attached_reports"] == [late["report_id"]]
    assert state.values["outcome"] == "promoted"
    assert harness.publisher.steps(run_id).count("approval_requested") == 1


async def test_restart_resumes_from_the_shared_checkpointer(drift_report):
    harness = make_harness()
    _, run_id = await waiting_run(harness, drift_report)

    restarted = RunManager(harness.graph(), harness.deps)
    await restarted.recover()
    assert restarted.active_run_id == run_id
    assert await restarted.on_drift_detected(drift_report | {"report_id": str(uuid.uuid4())}) == (
        run_id
    )
    assert await restarted.on_command(command(run_id))
    await restarted.wait_idle()

    assert harness.aliases.moves == ["4"]
    assert harness.publisher.steps(run_id)[-3:] == ["approved", "promoted", "completed"]
    assert harness.publisher.steps(run_id).count("approval_requested") == 1
    assert restarted.active_run_id is None


async def test_command_for_a_run_unknown_to_this_process_is_recovered(drift_report):
    harness = make_harness()
    _, run_id = await waiting_run(harness, drift_report)

    restarted = RunManager(harness.graph(), harness.deps)
    assert await restarted.on_command(command(run_id, "reject", "not this week"))
    await restarted.wait_idle()
    assert restarted.list_runs()[0]["outcome"] == "rejected"
