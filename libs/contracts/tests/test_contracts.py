import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = sorted((ROOT / "events").glob("*.json"))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.mark.parametrize("schema_path", SCHEMAS, ids=lambda p: p.stem)
def test_schema_is_valid(schema_path: Path) -> None:
    Draft202012Validator.check_schema(load(schema_path))


@pytest.mark.parametrize("schema_path", SCHEMAS, ids=lambda p: p.stem)
def test_example_matches_schema(schema_path: Path) -> None:
    example = load(ROOT / "examples" / schema_path.name)
    Draft202012Validator(load(schema_path), format_checker=FormatChecker()).validate(example)


def test_every_topic_has_a_versioned_schema() -> None:
    topics = {p.name.rsplit(".v", 1)[0] for p in SCHEMAS}
    assert topics == {
        "transaction.raw",
        "transaction.scored",
        "drift.detected",
        "agent.events",
        "agent.commands",
        "model.promoted",
    }


def test_reject_requires_reason() -> None:
    schema = load(ROOT / "events" / "agent.commands.v1.json")
    command = load(ROOT / "examples" / "agent.commands.v1.json")
    command |= {"action": "reject", "reason": None}
    assert list(Draft202012Validator(schema).iter_errors(command))


def test_raw_rejects_missing_feature() -> None:
    schema = load(ROOT / "events" / "transaction.raw.v1.json")
    payload = load(ROOT / "examples" / "transaction.raw.v1.json")
    payload.pop("v14")
    assert list(Draft202012Validator(schema).iter_errors(payload))


def test_openapi_predict_requires_features() -> None:
    spec = yaml.safe_load((ROOT / "openapi" / "inference.v1.yaml").read_text())
    request = spec["components"]["schemas"]["PredictRequest"]
    assert set(request["required"]) == {"transaction_id", "amount", "features"}
