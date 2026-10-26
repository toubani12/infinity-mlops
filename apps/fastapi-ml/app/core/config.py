from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    model_name: str = "fraud-xgb"
    model_alias: str = "champion"
    mlflow_tracking_uri: str = "http://localhost:5000"
    fraud_threshold: float = Field(default=0.5, ge=0, le=1)
    model_retry_seconds: float = Field(default=15.0, gt=0)

    prediction_log_enabled: bool = True
    prediction_log_uri: str = "s3://predictions"
    prediction_log_max_rows: int = Field(default=1000, ge=1)
    prediction_log_max_seconds: float = Field(default=60.0, gt=0)
    s3_endpoint_url: str | None = None

    kafka_enabled: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "fastapi-ml"
    kafka_input_topic: str = "transaction.raw"
    kafka_output_topic: str = "transaction.scored"
    kafka_batch_size: int = Field(default=64, ge=1, le=1000)
    kafka_max_wait_ms: int = Field(default=50, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
