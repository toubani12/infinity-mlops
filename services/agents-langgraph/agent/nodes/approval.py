from agent.deps import AgentDeps
from agent.state import AgentState


async def request_approval(state: AgentState, deps: AgentDeps) -> AgentState:
    event = await deps.tools.request_approval.request(
        state["run_id"],
        state["report"]["report_id"],
        state["champion"],
        state["challenger"],
        state["gate"],
    )
    return {"outcome": "awaiting_approval", "events": [event]}
