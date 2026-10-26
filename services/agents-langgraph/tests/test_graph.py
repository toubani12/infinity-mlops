import uuid

from agent.graph import thread
from tests.conftest import make_harness
from tests.fakes import FakeMetricsReader, FakeRetrainLauncher, metrics


async def run_graph(harness, report: dict) -> tuple[str, dict]:
    run_id = str(uuid.uuid4())
    initial = {"run_id": run_id, "report": report, "attached_reports": [], "events": []}
    state = await harness.graph().ainvoke(initial, thread(run_id))
    return run_id, state


async def test_noise_ends_without_retraining(harness, drift_report):
    quiet = drift_report | {
        "drift_share": 0.12,
        "metrics": {"pr_auc": 0.83, "reference_pr_auc": 0.84},
    }
    run_id, state = await run_graph(harness, quiet)

    assert state["qualification"] == "noise"
    assert state["outcome"] == "noise"
    assert harness.publisher.steps(run_id) == ["received", "qualified", "completed"]
    assert harness.launcher.launched == []
    harness.assert_events_match_contract()


async def test_data_incident_escalates_without_retraining(harness, drift_report):
    broken = drift_report | {"missing_features": ["v14", "amount"]}
    run_id, state = await run_graph(harness, broken)

    assert state["outcome"] == "escalated"
    assert harness.publisher.steps(run_id) == ["received", "qualified", "escalated", "completed"]
    escalated = harness.publisher.on("agent.events")[2]
    assert escalated["decision"] == "data_incident"
    assert escalated["payload"]["missing_features"] == ["v14", "amount"]
    assert harness.launcher.launched == []
    harness.assert_events_match_contract()


async def test_real_drift_with_better_challenger_requests_approval(harness, drift_report):
    run_id, state = await run_graph(harness, drift_report)

    assert state["qualification"] == "real_drift"
    assert state["retrain_job"] == {"name": f"retrain-{run_id[:8]}", "status": "succeeded"}
    assert state["gate"]["passed"]
    assert state["decision"] == "promote"
    assert state["outcome"] == "awaiting_approval"
    assert harness.publisher.steps(run_id) == [
        "received",
        "qualified",
        "retrain_started",
        "retrain_finished",
        "evaluated",
        "approval_requested",
    ]
    request = harness.publisher.on("agent.events")[-1]
    assert request["requires_approval"] is True
    assert request["payload"]["champion"]["version"] == "3"
    assert request["payload"]["challenger"]["version"] == "4"
    assert [event["step"] for event in state["events"]] == harness.publisher.steps(run_id)
    harness.assert_events_match_contract()


async def test_worse_challenger_keeps_the_champion(drift_report):
    worse = FakeMetricsReader(
        {
            "challenger": metrics("4", 0.69, 0.50, 6.4),
            "champion": metrics("3", 0.71, 0.52, 6.1),
            "gate_passed": False,
            "gate_reasons": "pr_auc and recall below champion",
        }
    )
    harness = make_harness(metrics=worse)
    run_id, state = await run_graph(harness, drift_report)

    assert state["decision"] == "keep_champion"
    assert state["outcome"] == "kept_champion"
    assert harness.publisher.steps(run_id)[-2:] == ["evaluated", "completed"]
    completed = harness.publisher.on("agent.events")[-1]
    assert completed["decision"] == "keep_champion"
    assert "pr_auc 0.690 <= champion 0.710" in completed["message"]
    assert harness.aliases.moves == []
    harness.assert_events_match_contract()


async def test_failed_retrain_job_fails_the_run(drift_report):
    harness = make_harness(launcher=FakeRetrainLauncher(status="failed"))
    run_id, state = await run_graph(harness, drift_report)

    assert state["outcome"] == "failed"
    assert harness.publisher.steps(run_id) == ["received", "qualified", "retrain_started", "failed"]
    failed = harness.publisher.on("agent.events")[-1]
    assert failed["message"] == "BackoffLimitExceeded"
    assert failed["payload"]["job_name"] == f"retrain-{run_id[:8]}"
    harness.assert_events_match_contract()


async def test_every_event_is_keyed_by_run_id(harness, drift_report):
    run_id, _ = await run_graph(harness, drift_report)
    assert {key for _, key, _ in harness.publisher.sent} == {run_id}
