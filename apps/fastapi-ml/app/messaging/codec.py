import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from app.inference.model import V_FEATURES
from app.inference.service import Score, Transaction


class InvalidMessageError(ValueError):
    pass


class _RawBase(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


RawTransaction = create_model(
    "RawTransaction",
    __base__=_RawBase,
    transaction_id=(UUID, ...),
    timestamp=(datetime, ...),
    amount=(float, Field(ge=0)),
    label=(int | None, Field(default=None, ge=0, le=1)),
    **{name: (float, ...) for name in V_FEATURES},
)


def decode_raw(value: bytes | None) -> Transaction:
    if not value:
        raise InvalidMessageError("empty message")
    try:
        raw: Any = RawTransaction.model_validate_json(value)
    except ValidationError as error:
        raise InvalidMessageError(error.errors(include_url=False)) from error
    return Transaction(
        transaction_id=str(raw.transaction_id),
        timestamp=raw.timestamp,
        features={name: getattr(raw, name) for name in [*V_FEATURES, "amount"]},
        label=raw.label,
    )


def encode_scored(score: Score, scored_at: datetime | None = None) -> bytes:
    payload = {
        "transaction_id": score.transaction_id,
        "timestamp": (scored_at or datetime.now(UTC)).isoformat().replace("+00:00", "Z"),
        "fraud_score": score.fraud_score,
        "is_fraud": score.is_fraud,
        "threshold": score.threshold,
        "model_name": score.model_name,
        "model_version": score.model_version,
        "latency_ms": score.latency_ms,
    }
    return json.dumps(payload).encode()
