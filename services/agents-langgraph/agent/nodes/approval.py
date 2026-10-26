import asyncio

from langgraph.types import interrupt

from agent.deps import AgentDeps
from agent.state import AgentState, Approval


async def request_approval(state: AgentState, deps: AgentDeps) -> AgentState:
    event = await deps.tools.request_approval.request(
        state["run_id"],
        state["report"]["report_id"],
        state["champion"],
        state["challenger"],
        state["gate"],
    )
    return {"outcome": "awaiting_approval", "events": [event]}


# Kept apart from request_approval: LangGraph re-runs the interrupted node from its start on
# resume, which would publish approval_requested a second time.
async def await_approval(state: AgentState, deps: AgentDeps) -> AgentState:
    answer = interrupt(
        {
            "run_id": state["run_id"],
            "champion": state["champion"],
            "challenger": state["challenger"],
        }
    )
    approval: Approval = {
        "actor": answer["actor"],
        "action": answer["action"],
        "reason": answer.get("reason"),
    }
    approved = approval["action"] == "approve"
    event = await deps.emitter.emit(
        state["run_id"],
        "approved" if approved else "rejected",
        decision="promote" if approved else "keep_champion",
        message=f"{approval['action']} by {approval['actor']}"
        + (f": {approval['reason']}" if approval["reason"] else ""),
        payload={
            "actor": approval["actor"],
            "reason": approval["reason"],
            "command_id": answer.get("command_id"),
        },
    )
    return {"approval": approval, "events": [event]}


async def promote(state: AgentState, deps: AgentDeps) -> AgentState:
    run_id = state["run_id"]
    version = state["challenger"]["version"]
    model_name = deps.settings.model_name
    previous = await asyncio.to_thread(deps.tools.move_alias.move_champion, version)
    await deps.emitter.model_promoted(run_id, model_name, version, previous, reason="promotion")
    promoted = await deps.emitter.emit(
        run_id,
        "promoted",
        decision="promote",
        message=f"{model_name}@champion moved from {previous} to {version}",
        payload={"model_name": model_name, "version": version, "previous_version": previous},
    )
    completed = await deps.emitter.emit(
        run_id,
        "completed",
        decision="promote",
        message=f"version {version} is the champion",
        payload={"report_id": state["report"]["report_id"]},
    )
    return {
        "promoted_version": version,
        "previous_version": previous,
        "outcome": "promoted",
        "events": [promoted, completed],
    }


async def reject(state: AgentState, deps: AgentDeps) -> AgentState:
    reason = state["approval"]["reason"]
    completed = await deps.emitter.emit(
        state["run_id"],
        "completed",
        decision="keep_champion",
        message=f"champion kept after rejection: {reason}",
        payload={"report_id": state["report"]["report_id"]},
    )
    return {"outcome": "rejected", "events": [completed]}
