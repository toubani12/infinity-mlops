from pathlib import Path

import pytest
import yaml
from kubernetes.client import (
    V1Job,
    V1JobCondition,
    V1JobStatus,
    V1ObjectMeta,
    V1Pod,
    V1PodList,
)
from kubernetes.client.exceptions import ApiException

from agent.config import Settings
from agent.tools.retrain_job import (
    InvalidTemplate,
    KubernetesRetrainLauncher,
    build_job,
    load_template,
)

TEMPLATE = Path(__file__).parent / "fixtures" / "retrain-job.yaml"
RUN_ID = "5b2c7d8e-9f0a-4b1c-8d2e-3f4a5b6c7d8e"


def settings(**overrides) -> Settings:
    values = {"retrain_template_path": str(TEMPLATE), "retrain_poll_seconds": 10.0}
    return Settings(_env_file=None, **(values | overrides))


def job_with(*conditions: tuple[str, str], succeeded: int | None = None) -> V1Job:
    return V1Job(
        status=V1JobStatus(
            succeeded=succeeded,
            conditions=[
                V1JobCondition(type=kind, status="True", reason=reason)
                for kind, reason in conditions
            ],
        )
    )


class FakeBatchApi:
    def __init__(self, statuses: list[V1Job] | None = None, create_error: int | None = None):
        self.created: list[tuple[str, dict]] = []
        self.reads: list[tuple[str, str]] = []
        self._statuses = statuses or []
        self._create_error = create_error

    def create_namespaced_job(self, namespace: str, body: dict) -> V1Job:
        if self._create_error:
            raise ApiException(status=self._create_error, reason="nope")
        self.created.append((namespace, body))
        return V1Job(metadata=V1ObjectMeta(name=body["metadata"]["name"]))

    def read_namespaced_job(self, name: str, namespace: str) -> V1Job:
        self.reads.append((name, namespace))
        return self._statuses.pop(0) if len(self._statuses) > 1 else self._statuses[0]


class FakeCoreApi:
    def __init__(self, log: str = "", pods: int = 1, error: bool = False) -> None:
        self.log, self.pods, self.error = log, pods, error
        self.selectors: list[str] = []

    def list_namespaced_pod(self, namespace: str, label_selector: str) -> V1PodList:
        self.selectors.append(label_selector)
        if self.error:
            raise ApiException(status=403, reason="Forbidden")
        names = [f"retrain-5b2c7d8e-{i}" for i in range(self.pods)]
        return V1PodList(items=[V1Pod(metadata=V1ObjectMeta(name=n)) for n in names])

    def read_namespaced_pod_log(self, name, namespace, container, tail_lines) -> str:
        assert (container, tail_lines) == ("trainer", 5)
        return self.log


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def launcher(batch: FakeBatchApi, core: FakeCoreApi | None = None, clock=None, **overrides):
    clock = clock or FakeClock()
    return KubernetesRetrainLauncher(
        settings(**overrides),
        batch_api=lambda: batch,
        core_api=(lambda: core) if core else None,
        clock=clock,
        sleep=clock.sleep,
    )


def test_build_job_patches_only_name_labels_and_contract_env():
    template = load_template(str(TEMPLATE))
    job = build_job(template, RUN_ID, settings(retrain_window_days=14))

    assert job["metadata"]["name"] == "retrain-5b2c7d8e"
    assert job["metadata"]["namespace"] == "infinity"
    assert job["metadata"]["labels"] == {
        "app.kubernetes.io/part-of": "infinity-mlops",
        "app.kubernetes.io/component": "retrain",
        "infinity.io/run-id": RUN_ID,
    }
    pod = job["spec"]["template"]
    assert pod["metadata"]["labels"]["infinity.io/run-id"] == RUN_ID
    trainer = pod["spec"]["containers"][0]
    assert {e["name"]: e["value"] for e in trainer["env"]} == {
        "LOG_LEVEL": "INFO",
        "RUN_ID": RUN_ID,
        "WINDOW_DAYS": "14",
        "TRAIN_CONFIG": "configs/xgb_baseline.yaml",
        "DATA_URI": "s3://datasets/raw/creditcard.parquet",
        "PREDICTIONS_URI": "s3://predictions/",
    }
    assert trainer["envFrom"] == template["spec"]["template"]["spec"]["containers"][0]["envFrom"]
    assert job["spec"]["backoffLimit"] == 0
    assert job["spec"]["activeDeadlineSeconds"] == 1800
    assert template["metadata"]["name"] == "retrain-template"


def test_template_must_be_a_job_with_a_trainer_container(tmp_path):
    with pytest.raises(InvalidTemplate, match="batch/v1 Job"):
        build_job({"apiVersion": "v1", "kind": "Pod"}, RUN_ID, settings())
    template = load_template(str(TEMPLATE))
    template["spec"]["template"]["spec"]["containers"][0]["name"] = "shell"
    with pytest.raises(InvalidTemplate, match="trainer"):
        build_job(template, RUN_ID, settings())
    with pytest.raises(InvalidTemplate, match="not found"):
        load_template(str(tmp_path / "missing.yaml"))


def test_launch_creates_the_job_in_the_agent_namespace():
    batch = FakeBatchApi()
    assert launcher(batch).launch(RUN_ID) == "retrain-5b2c7d8e"
    namespace, body = batch.created[0]
    assert namespace == "infinity"
    assert yaml.safe_dump(body)


def test_launch_is_idempotent_when_the_job_already_exists():
    assert launcher(FakeBatchApi(create_error=409)).launch(RUN_ID) == "retrain-5b2c7d8e"


def test_launch_surfaces_other_api_errors():
    with pytest.raises(ApiException):
        launcher(FakeBatchApi(create_error=403)).launch(RUN_ID)


def test_wait_polls_until_the_job_completes():
    batch = FakeBatchApi([V1Job(status=V1JobStatus(active=1))] * 2 + [job_with(("Complete", ""))])
    clock = FakeClock()
    job = launcher(batch, clock=clock).wait("retrain-5b2c7d8e")

    assert job == {"name": "retrain-5b2c7d8e", "status": "succeeded", "message": "job complete"}
    assert clock.sleeps == [10.0, 10.0]
    assert batch.reads[0] == ("retrain-5b2c7d8e", "infinity")


def test_succeeded_count_without_condition_counts_as_success():
    job = launcher(FakeBatchApi([job_with(succeeded=1)])).wait("retrain-5b2c7d8e")
    assert job["status"] == "succeeded"


def test_failed_job_reports_the_reason_and_the_log_tail():
    core = FakeCoreApi(log="loading data\nKeyError: 'label'\n")
    batch = FakeBatchApi([job_with(("Failed", "BackoffLimitExceeded"))])
    job = launcher(batch, core).wait("retrain-5b2c7d8e")

    assert job["status"] == "failed"
    assert job["message"] == "BackoffLimitExceeded: loading data\nKeyError: 'label'"
    assert core.selectors == ["job-name=retrain-5b2c7d8e"]


def test_log_errors_do_not_hide_the_failure_reason():
    batch = FakeBatchApi([job_with(("Failed", "DeadlineExceeded"))])
    assert launcher(batch, FakeCoreApi(error=True)).wait("x")["message"] == "DeadlineExceeded"
    assert launcher(batch, FakeCoreApi(pods=0)).wait("x")["message"] == "DeadlineExceeded"


def test_wait_gives_up_at_the_deadline():
    batch = FakeBatchApi([V1Job(status=None)])
    job = launcher(batch, retrain_timeout_seconds=30).wait("retrain-5b2c7d8e")
    assert job == {
        "name": "retrain-5b2c7d8e",
        "status": "failed",
        "message": "no result after 30 s",
    }


def test_conditions_that_are_not_true_are_ignored():
    pending = V1Job(status=V1JobStatus(conditions=[V1JobCondition(type="Failed", status="False")]))
    batch = FakeBatchApi([pending, job_with(("Complete", ""))])
    assert launcher(batch).wait("x")["status"] == "succeeded"


def test_agent_code_has_no_shell_access():
    source = (Path(__file__).parents[1] / "agent").rglob("*.py")
    forbidden = ("subprocess", "os.system", "kubectl", "shell=True")
    offenders = [
        (path.name, word) for path in source for word in forbidden if word in path.read_text()
    ]
    assert offenders == []
