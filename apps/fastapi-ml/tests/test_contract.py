import yaml
from jsonschema import Draft202012Validator

from tests.conftest import CONTRACTS, transaction_payload

SPEC = yaml.safe_load((CONTRACTS / "openapi" / "inference.v1.yaml").read_text())


def schema(name: str) -> dict:
    return SPEC["components"]["schemas"][name]


def test_app_exposes_exactly_the_contract_paths(client) -> None:
    exposed = client.get("/openapi.json").json()["paths"]
    assert {path: set(ops) for path, ops in exposed.items()} == {
        path: set(ops) for path, ops in SPEC["paths"].items()
    }
    for path, operations in SPEC["paths"].items():
        for method, operation in operations.items():
            assert exposed[path][method]["operationId"] == operation["operationId"]


def test_contract_request_example_is_accepted(client) -> None:
    payload = transaction_payload()
    Draft202012Validator(schema("PredictRequest")).validate(payload)
    response = client.post("/predict", json=payload)
    Draft202012Validator(schema("PredictResponse")).validate(response.json())


def test_model_info_and_health_match_contract(client) -> None:
    Draft202012Validator(schema("ModelInfo")).validate(client.get("/model").json())
    Draft202012Validator(schema("ModelInfo")).validate(client.post("/model/reload").json())
    health = SPEC["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]
    Draft202012Validator(health["schema"]).validate(client.get("/health").json())
