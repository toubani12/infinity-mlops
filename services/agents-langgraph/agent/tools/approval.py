from agent.events import EventEmitter
from agent.state import EmittedEvent, GateResult, ModelMetrics


class EventApprovalRequester:
    """request_approval: publishes the request on agent.events, where the dashboard picks it up."""

    def __init__(self, emitter: EventEmitter) -> None:
        self._emitter = emitter

    async def request(
        self,
        run_id: str,
        report_id: str,
        champion: ModelMetrics | None,
        challenger: ModelMetrics,
        gate: GateResult,
    ) -> EmittedEvent:
        return await self._emitter.emit(
            run_id,
            "approval_requested",
            decision="promote",
            requires_approval=True,
            message="; ".join(gate["reasons"]),
            payload={"report_id": report_id, "champion": champion, "challenger": challenger},
        )
