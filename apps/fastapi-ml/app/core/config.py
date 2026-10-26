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


@lru_cache
def get_settings() -> Settings:
    return Settings()
