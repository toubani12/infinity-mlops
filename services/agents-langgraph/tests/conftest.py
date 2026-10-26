import copy
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from langgraph.checkpoint.memory import InMemorySaver

from agent.config import Settings
from agent.deps import AgentDeps
from agent.events import EventEmitter
from agent.graph import build_graph
from agent.runs import RunManager
from agent.tools import Toolset
from agent.tools.approval import EventApprovalRequester
from agent.tools.report import PayloadReportReader
from tests.fakes import FakeAliasMover, FakeMetricsReader, FakeRetrainLauncher, RecordingPublisher

CONTRACTS = Path(__file__).resolve().parents[3] / "libs" / "contracts"


def contract_example(topic: str) -> dict:
    return json.loads((CONTRACTS / "examples" / f"{topic}.v1.json").read_text())


def validator(topic: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS / "events" / f"{topic}.v1.json").read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def drift_report() -> dict:
    return copy.deepcopy(contract_example("drift.detected"))


@dataclass
class Harness:
    publisher: RecordingPublisher
    launcher: FakeRetrainLauncher
    metrics: FakeMetricsReader
    aliases: FakeAliasMover
    deps: AgentDeps
    checkpointer: InMemorySaver

    def graph(self):
        return build_graph(self.deps, self.checkpointer)

    def manager(self) -> RunManager:
        return RunManager(self.graph(), self.deps)

    def assert_events_match_contract(self) -> None:
        events = validator("agent.events")
        for event in self.publisher.on("agent.events"):
            events.validate(event)


def make_harness(
    launcher: FakeRetrainLauncher | None = None,
    metrics: FakeMetricsReader | None = None,
    settings: Settings | None = None,
    explainer=None,
) -> Harness:
    publisher = RecordingPublisher()
    emitter = EventEmitter(publisher, "agent.events")
    launcher = launcher or FakeRetrainLauncher()
    metrics = metrics or FakeMetricsReader()
    aliases = FakeAliasMover()
    tools = Toolset(
        read_report=PayloadReportReader(),
        launch_retrain_job=launcher,
        read_mlflow_metrics=metrics,
        request_approval=EventApprovalRequester(emitter),
        move_alias=aliases,
    )
    deps = AgentDeps(settings=settings or Settings(_env_file=None), tools=tools, emitter=emitter)
    if explainer is not None:
        deps.explainer = explainer
    return Harness(publisher, launcher, metrics, aliases, deps, InMemorySaver())


@pytest.fixture
def harness() -> Harness:
    return make_harness()
