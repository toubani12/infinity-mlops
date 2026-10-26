from functools import cache

from kubernetes import client as k8s
from kubernetes import config as k8s_config
from mlflow import MlflowClient

from agent.config import Settings
from agent.events import EventEmitter
from agent.tools import Toolset
from agent.tools.approval import EventApprovalRequester
from agent.tools.registry import MlflowAliasMover, MlflowMetricsReader
from agent.tools.report import PayloadReportReader
from agent.tools.retrain_job import KubernetesRetrainLauncher


@cache
def kubernetes_api_client() -> k8s.ApiClient:
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()
    return k8s.ApiClient()


def build_toolset(settings: Settings, emitter: EventEmitter) -> Toolset:
    registry = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    return Toolset(
        read_report=PayloadReportReader(),
        launch_retrain_job=KubernetesRetrainLauncher(
            settings,
            batch_api=lambda: k8s.BatchV1Api(kubernetes_api_client()),
            core_api=lambda: k8s.CoreV1Api(kubernetes_api_client()),
        ),
        read_mlflow_metrics=MlflowMetricsReader(registry, settings.model_name),
        request_approval=EventApprovalRequester(emitter),
        move_alias=MlflowAliasMover(registry, settings.model_name),
    )
