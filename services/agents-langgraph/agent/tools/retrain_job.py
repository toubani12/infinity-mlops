"""launch_retrain_job: create the retrain Job from the shared template and follow it to the end.

The manifest follows docs/architecture/retrain-contract.md. Only the name, labels and the
documented env vars of container `trainer` are patched; everything else comes from the template.
"""

import copy
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import yaml
from kubernetes.client.exceptions import ApiException

from agent.config import Settings
from agent.state import RetrainJob

log = logging.getLogger(__name__)

TRAINER = "trainer"
RUN_ID_LABEL = "infinity.io/run-id"


class InvalidTemplate(ValueError):
    pass


class BatchApi(Protocol):
    def create_namespaced_job(self, namespace: str, body: dict) -> Any: ...

    def read_namespaced_job(self, name: str, namespace: str) -> Any: ...


class CoreApi(Protocol):
    def list_namespaced_pod(self, namespace: str, label_selector: str) -> Any: ...

    def read_namespaced_pod_log(
        self, name: str, namespace: str, container: str, tail_lines: int
    ) -> str: ...


def job_name_for(run_id: str) -> str:
    return f"retrain-{run_id[:8]}"


def load_template(path: str) -> dict:
    file = Path(path)
    if not file.is_file():
        raise InvalidTemplate(f"retrain template not found at {path}")
    return yaml.safe_load(file.read_text())


def trainer_env(run_id: str, settings: Settings) -> dict[str, str]:
    return {
        "RUN_ID": run_id,
        "WINDOW_DAYS": str(settings.retrain_window_days),
        "TRAIN_CONFIG": settings.retrain_train_config,
        "DATA_URI": settings.retrain_data_uri,
        "PREDICTIONS_URI": settings.retrain_predictions_uri,
    }


def build_job(template: dict, run_id: str, settings: Settings) -> dict:
    if template.get("apiVersion") != "batch/v1" or template.get("kind") != "Job":
        raise InvalidTemplate("retrain template must be a batch/v1 Job")
    job = copy.deepcopy(template)
    metadata = job.setdefault("metadata", {})
    metadata["name"] = job_name_for(run_id)
    metadata["namespace"] = settings.k8s_namespace
    metadata.setdefault("labels", {})[RUN_ID_LABEL] = run_id
    pod = job["spec"]["template"]
    pod.setdefault("metadata", {}).setdefault("labels", {})[RUN_ID_LABEL] = run_id

    containers = [c for c in pod["spec"]["containers"] if c.get("name") == TRAINER]
    if not containers:
        raise InvalidTemplate(f"retrain template has no container named {TRAINER}")
    overrides = trainer_env(run_id, settings)
    env = [e for e in containers[0].get("env", []) if e.get("name") not in overrides]
    containers[0]["env"] = env + [{"name": k, "value": v} for k, v in overrides.items()]
    return job


def job_outcome(job: Any) -> tuple[str, str] | None:
    status = job.status
    if status is None:
        return None
    for condition in status.conditions or []:
        if condition.status != "True":
            continue
        if condition.type == "Complete":
            return "succeeded", "job complete"
        if condition.type == "Failed":
            return "failed", condition.reason or condition.message or "job failed"
    if status.succeeded:
        return "succeeded", "job complete"
    return None


class KubernetesRetrainLauncher:
    def __init__(
        self,
        settings: Settings,
        batch_api: Callable[[], BatchApi],
        core_api: Callable[[], CoreApi] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._batch_api = batch_api
        self._core_api = core_api
        self._clock = clock
        self._sleep = sleep

    def launch(self, run_id: str) -> str:
        job = build_job(load_template(self._settings.retrain_template_path), run_id, self._settings)
        name = job["metadata"]["name"]
        try:
            self._batch_api().create_namespaced_job(self._settings.k8s_namespace, job)
        except ApiException as exc:
            if exc.status != 409:
                raise
            log.info("job %s already exists, following it", name)
        return name

    def wait(self, job_name: str) -> RetrainJob:
        namespace = self._settings.k8s_namespace
        deadline = self._clock() + self._settings.retrain_timeout_seconds
        api = self._batch_api()
        while True:
            outcome = job_outcome(api.read_namespaced_job(job_name, namespace))
            if outcome is not None:
                status, message = outcome
                if status == "failed":
                    message = self._with_log_tail(job_name, message)
                return {"name": job_name, "status": status, "message": message}
            if self._clock() >= deadline:
                return {
                    "name": job_name,
                    "status": "failed",
                    "message": f"no result after {self._settings.retrain_timeout_seconds:.0f} s",
                }
            self._sleep(self._settings.retrain_poll_seconds)

    def _with_log_tail(self, job_name: str, message: str) -> str:
        if self._core_api is None:
            return message
        namespace = self._settings.k8s_namespace
        try:
            api = self._core_api()
            pods = api.list_namespaced_pod(namespace, label_selector=f"job-name={job_name}").items
            if not pods:
                return message
            tail = api.read_namespaced_pod_log(
                pods[-1].metadata.name, namespace, container=TRAINER, tail_lines=5
            )
        except ApiException as exc:
            log.warning("could not read logs of %s: %s", job_name, exc.reason)
            return message
        return f"{message}: {tail.strip()[-500:]}" if tail.strip() else message
