import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS = Path(__file__).resolve().parents[3] / "libs" / "contracts"


def contract_example(topic: str) -> dict:
    return json.loads((CONTRACTS / "examples" / f"{topic}.v1.json").read_text())


def validator(topic: str) -> Draft202012Validator:
    schema = json.loads((CONTRACTS / "events" / f"{topic}.v1.json").read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def drift_report() -> dict:
    return copy.deepcopy(contract_example("drift.detected"))
