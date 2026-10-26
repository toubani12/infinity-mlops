from agent.config import Settings
from agent.events import EventEmitter
from agent.tools import Toolset
from agent.tools.approval import EventApprovalRequester
from agent.tools.report import PayloadReportReader


class ToolNotConfigured:
    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str):
        raise RuntimeError(f"tool {self._name} is not configured in this build")


def build_toolset(settings: Settings, emitter: EventEmitter) -> Toolset:
    return Toolset(
        read_report=PayloadReportReader(),
        launch_retrain_job=ToolNotConfigured("launch_retrain_job"),
        read_mlflow_metrics=ToolNotConfigured("read_mlflow_metrics"),
        request_approval=EventApprovalRequester(emitter),
        move_alias=ToolNotConfigured("move_alias"),
    )
