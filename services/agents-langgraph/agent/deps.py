from collections import defaultdict
from dataclasses import dataclass, field

from agent.config import Settings
from agent.events import EventEmitter
from agent.llm import Explainer, NoExplainer
from agent.tools import Toolset


class AttachmentInbox:
    """Alerts attached to a busy run; the next node of that run folds them into its state."""

    def __init__(self) -> None:
        self._pending: defaultdict[str, list[str]] = defaultdict(list)

    def put(self, run_id: str, report_id: str) -> None:
        self._pending[run_id].append(report_id)

    def drain(self, run_id: str) -> list[str]:
        return self._pending.pop(run_id, [])


@dataclass
class AgentDeps:
    settings: Settings
    tools: Toolset
    emitter: EventEmitter
    explainer: Explainer = field(default_factory=NoExplainer)
    inbox: AttachmentInbox = field(default_factory=AttachmentInbox)
