import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Literal

from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from agent.commands import AgentCommand, InvalidCommand
from agent.deps import AgentDeps
from agent.events import utc_now
from agent.graph import thread
from agent.metrics import (
    ACTIVE_RUN,
    ALERTS_ATTACHED,
    DRIFT_ALERT_TIME,
    DRIFT_ALERTS,
    DRIFT_SHARE,
    RUNS_FINISHED,
    RUNS_STARTED,
)
from agent.tools.report import InvalidReport

log = logging.getLogger(__name__)

RUN_NAMESPACE = uuid.UUID("6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e5f")

RunStatus = Literal["running", "awaiting_approval", "finished"]

AWAITING = ("await_approval",)


def run_id_for(report_id: str) -> str:
    """Deterministic, so a redelivered drift.detected maps to the run it already started."""
    return str(uuid.uuid5(RUN_NAMESPACE, report_id))


@dataclass
class RunRecord:
    run_id: str
    report_id: str
    started_at: str
    status: RunStatus = "running"
    outcome: str | None = None
    attached_reports: list[str] = field(default_factory=list)


class RunManager:
    """Starts graph runs from drift alerts and holds the one-retrain-at-a-time guardrail."""

    def __init__(self, graph: CompiledStateGraph, deps: AgentDeps) -> None:
        self._graph = graph
        self._deps = deps
        self._runs: dict[str, RunRecord] = {}
        self._active: str | None = None
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    @property
    def active_run_id(self) -> str | None:
        return self._active

    def list_runs(self) -> list[dict]:
        return [asdict(record) for record in reversed(self._runs.values())]

    async def on_drift_detected(self, message: dict) -> str | None:
        try:
            report = self._deps.tools.read_report.read(message)
        except InvalidReport as exc:
            log.warning("ignoring invalid drift.detected: %s", exc)
            return None
        DRIFT_ALERTS.inc()
        DRIFT_SHARE.set(report.drift_share)
        DRIFT_ALERT_TIME.set_to_current_time()
        run_id = run_id_for(report.report_id)
        async with self._lock:
            if self._active is not None:
                if self._active != run_id:
                    await self._attach(self._active, report.report_id)
                return self._active
            if run_id in self._runs or await self._thread_exists(run_id):
                log.info("drift report %s already handled by run %s", report.report_id, run_id)
                return None
            self._start(run_id, report.report_id, message)
        return run_id

    async def on_command(self, message: dict) -> bool:
        try:
            command = AgentCommand.parse(message)
        except InvalidCommand as exc:
            log.warning("ignoring invalid agent.commands: %s", exc)
            return False
        async with self._lock:
            record = self._runs.get(command.run_id)
            if record is None and not await self._recover(command.run_id):
                log.info("ignoring %s for unknown run %s", command.action, command.run_id)
                return False
            record = self._runs[command.run_id]
            if record.status != "awaiting_approval":
                log.info("ignoring %s, run %s is %s", command.action, record.run_id, record.status)
                return False
            record.status = "running"
            resume = Command(resume=command.resume_value())
            self._spawn(record.run_id, self._graph.ainvoke(resume, thread(record.run_id)))
        return True

    async def recover(self) -> None:
        """After a restart, the run waiting for approval takes the retrain slot again."""
        # Collect first: the Postgres saver holds its connection while alist() is iterating.
        run_ids = {
            checkpoint.config["configurable"]["thread_id"]
            async for checkpoint in self._graph.checkpointer.alist(None)
        }
        for run_id in run_ids:
            await self._recover(run_id)
        waiting = [r for r in self._runs.values() if r.status == "awaiting_approval"]
        if waiting:
            self._active = max(waiting, key=lambda record: record.started_at).run_id

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks))

    def _start(self, run_id: str, report_id: str, message: dict) -> None:
        self._runs[run_id] = RunRecord(run_id, report_id, utc_now())
        self._active = run_id
        ACTIVE_RUN.set(1)
        RUNS_STARTED.inc()
        initial = {"run_id": run_id, "report": message, "attached_reports": [], "events": []}
        self._spawn(run_id, self._graph.ainvoke(initial, thread(run_id)))

    def _spawn(self, run_id: str, invocation) -> None:
        task = asyncio.create_task(self._drive(run_id, invocation))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _recover(self, run_id: str) -> bool:
        snapshot = await self._graph.aget_state(thread(run_id))
        if snapshot.next != AWAITING:
            return False
        values = snapshot.values
        self._runs[run_id] = RunRecord(
            run_id,
            values["report"]["report_id"],
            snapshot.created_at or utc_now(),
            status="awaiting_approval",
            outcome="awaiting_approval",
            attached_reports=list(values.get("attached_reports", [])),
        )
        self._active = run_id
        ACTIVE_RUN.set(1)
        return True

    async def _drive(self, run_id: str, invocation) -> None:
        try:
            result = await invocation
        except Exception as exc:
            log.exception("run %s failed", run_id)
            await self._report_failure(run_id, exc)
            self._finish(run_id, "failed")
            return
        outcome = result.get("outcome")
        if "__interrupt__" in result:
            self._runs[run_id].status = "awaiting_approval"
            self._runs[run_id].outcome = outcome
            return
        self._finish(run_id, outcome or "failed")

    def _finish(self, run_id: str, outcome: str) -> None:
        record = self._runs[run_id]
        record.status = "finished"
        record.outcome = outcome
        RUNS_FINISHED.labels(outcome=outcome).inc()
        if self._active == run_id:
            self._active = None
            ACTIVE_RUN.set(0)

    async def _attach(self, run_id: str, report_id: str) -> None:
        record = self._runs[run_id]
        if report_id in record.attached_reports:
            return
        record.attached_reports.append(report_id)
        ALERTS_ATTACHED.inc()
        if record.status == "running":
            self._deps.inbox.put(run_id, report_id)
        else:
            await self._graph.aupdate_state(thread(run_id), {"attached_reports": [report_id]})
        await self._deps.emitter.emit(
            run_id,
            "received",
            message="alert attached to the run in progress, no new retrain",
            payload={"report_id": report_id, "attached": True},
        )

    async def _thread_exists(self, run_id: str) -> bool:
        snapshot = await self._graph.aget_state(thread(run_id))
        return bool(snapshot.values)

    async def _report_failure(self, run_id: str, exc: Exception) -> None:
        try:
            await self._deps.emitter.emit(
                run_id,
                "failed",
                message=f"{type(exc).__name__}: {exc}",
                payload={"report_id": self._runs[run_id].report_id},
            )
        except Exception:
            log.exception("could not publish the failure of run %s", run_id)
