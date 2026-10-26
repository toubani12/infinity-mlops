import json
from datetime import UTC, datetime

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.inference.model import V_FEATURES
from app.inference.service import Score
from app.messaging.codec import InvalidMessageError, decode_raw, encode_scored
from tests.conftest import CONTRACTS, RAW_EXAMPLE, raw


def test_decode_raw_example_and_label() -> None:
    transaction = decode_raw(raw(label=1))
    assert transaction.label == 1
    assert list(transaction.features) == [*V_FEATURES, "amount"]
    assert decode_raw(RAW_EXAMPLE.encode()).label is None


@pytest.mark.parametrize(
    "value",
    [None, b"", b"{not json", raw(amount=-3), raw(v14="x"), raw(label=2), raw(transaction_id="1")],
)
def test_decode_rejects_poison(value) -> None:
    with pytest.raises(InvalidMessageError):
        decode_raw(value)


def test_encode_scored_matches_contract() -> None:
    score = Score(
        "7f8d4c2e-1b3a-4e5f-9a6b-0c1d2e3f4a5b",
        datetime.now(UTC),
        0.9,
        True,
        0.5,
        "fraud-xgb",
        "3",
        1.5,
    )
    event = json.loads(encode_scored(score, datetime(2026, 10, 26, 9, 15, tzinfo=UTC)))
    schema = json.loads((CONTRACTS / "events" / "transaction.scored.v1.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(event)
    assert event["timestamp"] == "2026-10-26T09:15:00Z"
