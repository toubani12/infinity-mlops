from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka_bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "agents-langgraph"
    drift_topic: str = "drift.detected"
    commands_topic: str = "agent.commands"
    events_topic: str = "agent.events"
    promoted_topic: str = "model.promoted"

    mlflow_tracking_uri: str = "http://localhost:5000"
    model_name: str = "fraud-xgb"
    database_url: str = ""

    llm_provider: Literal["none", "ollama", "anthropic", "openai"] = "none"
    llm_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: float = 20.0

    drift_share_threshold: float = 0.3
    pr_auc_drop_threshold: float = 0.05
    out_of_range_threshold: float = 0.05
    max_p95_latency_ms: float = 50.0

    k8s_namespace: str = "infinity"
    retrain_template_path: str = "/etc/agent/retrain/retrain-job.yaml"
    retrain_poll_seconds: float = 10.0
    # activeDeadlineSeconds of the template (1800) plus time to schedule and pull the image.
    retrain_timeout_seconds: float = 2100.0
    retrain_window_days: int = 7
    retrain_train_config: str = "configs/xgb_baseline.yaml"
    retrain_data_uri: str = "s3://datasets/raw/creditcard.parquet"
    retrain_predictions_uri: str = "s3://predictions/"

    http_port: int = 8100
