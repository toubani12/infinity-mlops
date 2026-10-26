from collections.abc import Awaitable, Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.deps import AgentDeps
from agent.nodes.approval import request_approval
from agent.nodes.intake import qualify, receive
from agent.nodes.retrain import evaluate, retrain
from agent.nodes.terminal import end_noise, escalate, fail, keep_champion
from agent.state import AgentState

NodeFn = Callable[[AgentState, AgentDeps], Awaitable[AgentState]]


def bind(fn: NodeFn, deps: AgentDeps) -> Callable[[AgentState], Awaitable[AgentState]]:
    async def node(state: AgentState) -> AgentState:
        update = await fn(state, deps)
        attached = deps.inbox.drain(state["run_id"])
        if attached:
            update = {**update, "attached_reports": attached}
        return update

    node.__name__ = fn.__name__
    return node


def thread(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def route_qualification(state: AgentState) -> str:
    return {"data_incident": "escalate", "noise": "end_noise"}.get(
        state["qualification"], "retrain"
    )


def route_retrain(state: AgentState) -> str:
    return "evaluate" if state["retrain_job"]["status"] == "succeeded" else "fail"


def route_decision(state: AgentState) -> str:
    return "request_approval" if state["decision"] == "promote" else "keep_champion"


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    builder = StateGraph(AgentState)
    for fn in (
        receive,
        qualify,
        escalate,
        end_noise,
        retrain,
        fail,
        evaluate,
        keep_champion,
        request_approval,
    ):
        builder.add_node(fn.__name__, bind(fn, deps))

    builder.add_edge(START, "receive")
    builder.add_edge("receive", "qualify")
    builder.add_conditional_edges(
        "qualify", route_qualification, ["escalate", "end_noise", "retrain"]
    )
    builder.add_conditional_edges("retrain", route_retrain, ["evaluate", "fail"])
    builder.add_conditional_edges("evaluate", route_decision, ["request_approval", "keep_champion"])
    for terminal in ("escalate", "end_noise", "fail", "keep_champion", "request_approval"):
        builder.add_edge(terminal, END)
    return builder.compile(checkpointer=checkpointer)
