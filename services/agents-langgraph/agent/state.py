import operator
from typing import Annotated, Literal, NotRequired, TypedDict

Qualification = Literal["noise", "real_drift", "data_incident"]
Decision = Literal["promote", "keep_champion"]
Outcome = Literal[
    "noise", "escalated", "kept_champion", "awaiting_approval", "promoted", "rejected", "failed"
]


class ModelMetrics(TypedDict):
    version: str | None
    pr_auc: float | None
    recall_at_p90: float | None
    p95_latency_ms: float | None


class RetrainJob(TypedDict):
    name: str
    status: Literal["running", "succeeded", "failed"]
    message: NotRequired[str]


class GateResult(TypedDict):
    passed: bool
    reasons: list[str]


class Approval(TypedDict):
    actor: str
    action: Literal["approve", "reject"]
    reason: str | None


class EmittedEvent(TypedDict):
    event_id: str
    step: str


class AgentState(TypedDict, total=False):
    run_id: str
    report: dict
    qualification: Qualification
    qualification_reasons: list[str]
    explanation: str | None
    retrain_job: RetrainJob
    champion: ModelMetrics | None
    challenger: ModelMetrics | None
    gate: GateResult
    decision: Decision
    approval: Approval
    promoted_version: str | None
    previous_version: str | None
    outcome: Outcome
    error: str
    attached_reports: Annotated[list[str], operator.add]
    events: Annotated[list[EmittedEvent], operator.add]
