import asyncio

from agent.deps import AgentDeps
from agent.rules import evaluate_gate
from agent.state import AgentState


async def retrain(state: AgentState, deps: AgentDeps) -> AgentState:
    run_id = state["run_id"]
    launcher = deps.tools.launch_retrain_job
    job_name = await asyncio.to_thread(launcher.launch, run_id)
    started = await deps.emitter.emit(
        run_id,
        "retrain_started",
        decision="real_drift",
        message=f"retrain job {job_name} created",
        payload={"report_id": state["report"]["report_id"], "job_name": job_name},
    )
    job = await asyncio.to_thread(launcher.wait, job_name)
    if job["status"] != "succeeded":
        return {
            "retrain_job": job,
            "error": job.get("message", f"retrain job {job_name} failed"),
            "events": [started],
        }
    finished = await deps.emitter.emit(
        run_id,
        "retrain_finished",
        message=f"retrain job {job_name} succeeded",
        payload={"job_name": job_name, "status": job["status"]},
    )
    return {"retrain_job": job, "events": [started, finished]}


async def evaluate(state: AgentState, deps: AgentDeps) -> AgentState:
    run_id = state["run_id"]
    evaluation = await asyncio.to_thread(deps.tools.read_mlflow_metrics.read, run_id)
    gate = evaluate_gate(evaluation, deps.settings.max_p95_latency_ms)
    decision = "promote" if gate["passed"] else "keep_champion"
    event = await deps.emitter.emit(
        run_id,
        "evaluated",
        decision=decision,
        message="; ".join(gate["reasons"]),
        payload={
            "report_id": state["report"]["report_id"],
            "champion": evaluation["champion"],
            "challenger": evaluation["challenger"],
            "gate": gate,
        },
    )
    return {
        "champion": evaluation["champion"],
        "challenger": evaluation["challenger"],
        "gate": gate,
        "decision": decision,
        "events": [event],
    }
