from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.inference.model import V_FEATURES

EXPECTED = set(V_FEATURES)


class PredictRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    transaction_id: UUID
    timestamp: datetime | None = None
    amount: float = Field(ge=0)
    features: dict[str, float]

    @field_validator("features")
    @classmethod
    def require_every_v_feature(cls, features: dict[str, float]) -> dict[str, float]:
        missing = sorted(EXPECTED - features.keys(), key=V_FEATURES.index)
        unexpected = sorted(features.keys() - EXPECTED)
        if missing or unexpected:
            raise ValueError(f"missing features {missing}, unexpected features {unexpected}")
        return features


class PredictResponse(BaseModel):
    transaction_id: UUID
    fraud_score: float
    is_fraud: bool
    threshold: float
    model_name: str
    model_version: str
    latency_ms: float


class ModelInfo(BaseModel):
    model_name: str
    version: str
    alias: str
    loaded_at: datetime
    threshold: float
    last_reload_error: str | None = None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    model_loaded: bool
