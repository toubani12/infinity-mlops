import threading

from agent.state import ModelMetrics, RetrainJob
from agent.tools import Evaluation


class RecordingPublisher:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict]] = []

    async def send(self, topic: str, key: str, value: dict) -> None:
        self.sent.append((topic, key, value))

    def on(self, topic: str) -> list[dict]:
        return [value for sent_topic, _, value in self.sent if sent_topic == topic]

    def steps(self, run_id: str | None = None) -> list[str]:
        return [
            event["step"]
            for event in self.on("agent.events")
            if run_id is None or event["run_id"] == run_id
        ]


class FakeRetrainLauncher:
    def __init__(self, status: str = "succeeded", release: threading.Event | None = None) -> None:
        self.status = status
        self.launched: list[str] = []
        self._release = release

    def launch(self, run_id: str) -> str:
        self.launched.append(run_id)
        return f"retrain-{run_id[:8]}"

    def wait(self, job_name: str) -> RetrainJob:
        if self._release is not None:
            assert self._release.wait(timeout=5)
        job: RetrainJob = {"name": job_name, "status": self.status}
        if self.status != "succeeded":
            job["message"] = "BackoffLimitExceeded"
        return job


def metrics(version: str, pr_auc: float, recall: float, latency: float) -> ModelMetrics:
    return {
        "version": version,
        "pr_auc": pr_auc,
        "recall_at_p90": recall,
        "p95_latency_ms": latency,
    }


class FakeMetricsReader:
    def __init__(self, evaluation: Evaluation | None = None) -> None:
        self.evaluation = evaluation or {
            "challenger": metrics("4", 0.83, 0.68, 6.4),
            "champion": metrics("3", 0.71, 0.52, 6.1),
            "gate_passed": True,
            "gate_reasons": "challenger beats champion",
        }

    def read(self, run_id: str) -> Evaluation:
        return self.evaluation


class FakeAliasMover:
    def __init__(self, current: str | None = "3") -> None:
        self.current = current
        self.moves: list[str] = []

    def move_champion(self, version: str) -> str | None:
        previous, self.current = self.current, version
        self.moves.append(version)
        return previous
