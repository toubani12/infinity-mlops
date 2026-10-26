from agent.deps import AgentDeps
from agent.state import AgentState


async def escalate(state: AgentState, deps: AgentDeps) -> AgentState:
    run_id = state["run_id"]
    report = state["report"]
    reasons = "; ".join(state["qualification_reasons"])
    escalated = await deps.emitter.emit(
        run_id,
        "escalated",
        decision="data_incident",
        message=f"data incident, no retraining: {reasons}",
        payload={
            "report_id": report["report_id"],
            "missing_features": report.get("missing_features", []),
            "out_of_range_share": report.get("out_of_range_share", 0.0),
        },
    )
    completed = await _completed(state, deps, "data_incident", "escalated to a human")
    return {"outcome": "escalated", "events": [escalated, completed]}


async def end_noise(state: AgentState, deps: AgentDeps) -> AgentState:
    completed = await _completed(state, deps, "noise", "alert qualified as noise")
    return {"outcome": "noise", "events": [completed]}


async def keep_champion(state: AgentState, deps: AgentDeps) -> AgentState:
    reasons = "; ".join(state["gate"]["reasons"])
    completed = await _completed(state, deps, "keep_champion", f"champion kept: {reasons}")
    return {"outcome": "kept_champion", "events": [completed]}


async def fail(state: AgentState, deps: AgentDeps) -> AgentState:
    error = state.get("error", "run failed")
    failed = await deps.emitter.emit(
        state["run_id"],
        "failed",
        message=error,
        payload={"report_id": state["report"]["report_id"], **_job_payload(state)},
    )
    return {"outcome": "failed", "events": [failed]}


async def _completed(state: AgentState, deps: AgentDeps, decision: str, message: str):
    return await deps.emitter.emit(
        state["run_id"],
        "completed",
        decision=decision,
        message=message,
        payload={"report_id": state["report"]["report_id"]},
    )


def _job_payload(state: AgentState) -> dict:
    job = state.get("retrain_job")
    return {"job_name": job["name"], "status": job["status"]} if job else {}
