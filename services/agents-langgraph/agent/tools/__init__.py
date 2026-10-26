"""The closed tool set of the agent. Nodes reach the outside world only through these interfaces."""

from dataclasses import dataclass
from typing import Protocol, TypedDict

from agent.state import EmittedEvent, GateResult, ModelMetrics, RetrainJob
from agent.tools.report import DriftReport


class Evaluation(TypedDict):
    challenger: ModelMetrics
    champion: ModelMetrics | None
    gate_passed: bool
    gate_reasons: str


class ReportReader(Protocol):
    def read(self, payload: dict) -> DriftReport: ...


class RetrainLauncher(Protocol):
    def launch(self, run_id: str) -> str: ...

    def wait(self, job_name: str) -> RetrainJob: ...


class MetricsReader(Protocol):
    def read(self, run_id: str) -> Evaluation: ...


class ApprovalRequester(Protocol):
    async def request(
        self,
        run_id: str,
        report_id: str,
        champion: ModelMetrics | None,
        challenger: ModelMetrics,
        gate: GateResult,
    ) -> EmittedEvent: ...


class AliasMover(Protocol):
    def move_champion(self, version: str) -> str | None: ...


@dataclass(frozen=True)
class Toolset:
    read_report: ReportReader
    launch_retrain_job: RetrainLauncher
    read_mlflow_metrics: MetricsReader
    request_approval: ApprovalRequester
    move_alias: AliasMover
