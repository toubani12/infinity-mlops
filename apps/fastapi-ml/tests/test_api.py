import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import StaticLoader, transaction_payload


def test_predict_scores_a_transaction(client) -> None:
    payload = transaction_payload()
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["transaction_id"] == payload["transaction_id"]
    assert 0 <= body["fraud_score"] <= 1
    assert body["model_version"] == "1" and body["model_name"] == "fraud-xgb"
    assert body["threshold"] == 0.5 and body["latency_ms"] >= 0


def test_fraud_pattern_is_flagged(client) -> None:
    fraud = client.post("/predict", json=transaction_payload(fraud=True)).json()
    legit = client.post("/predict", json=transaction_payload()).json()
    assert fraud["is_fraud"] and not legit["is_fraud"]
    assert fraud["fraud_score"] > legit["fraud_score"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["features"].pop("v14"),
        lambda p: p["features"].update(v29=1.0),
        lambda p: p.update(amount=-1),
        lambda p: p.update(transaction_id="not-a-uuid"),
        lambda p: p.pop("features"),
    ],
    ids=["missing-v14", "unexpected-v29", "negative-amount", "bad-id", "no-features"],
)
def test_invalid_payloads_are_rejected(client, mutate) -> None:
    payload = transaction_payload()
    mutate(payload)
    assert client.post("/predict", json=payload).status_code == 422


def test_missing_feature_is_named_in_the_error(client) -> None:
    payload = transaction_payload()
    del payload["features"]["v7"]
    assert "v7" in client.post("/predict", json=payload).text


def test_no_model_means_503_and_degraded_health(settings, predictor) -> None:
    loader = StaticLoader(predictor)
    loader.fail = True
    with TestClient(create_app(settings, loader)) as client:
        assert client.post("/predict", json=transaction_payload()).status_code == 503
        assert client.get("/model").status_code == 503
        assert client.get("/health").json() == {"status": "degraded", "model_loaded": False}
        loader.fail = False
        assert client.post("/model/reload").json()["version"] == "1"
        assert client.get("/health").json() == {"status": "ok", "model_loaded": True}


def test_reload_swaps_version(client) -> None:
    assert client.get("/model").json()["version"] == "1"
    reloaded = client.post("/model/reload").json()
    assert reloaded["version"] == "2" and reloaded["alias"] == "champion"
    assert client.post("/predict", json=transaction_payload()).json()["model_version"] == "2"


def test_failed_reload_keeps_previous_model(client, loader) -> None:
    loader.fail = True
    response = client.post("/model/reload")
    assert response.status_code == 503
    assert "previous model kept" in response.json()["detail"]
    assert client.get("/model").json()["version"] == "1"
    assert client.post("/predict", json=transaction_payload()).status_code == 200


def test_metrics_endpoint_exposes_inference_metrics(client) -> None:
    client.post("/predict", json=transaction_payload())
    text = client.get("/metrics").text
    assert 'http_request_duration_seconds_count{method="POST",path="/predict",status="200"}' in text
    assert "predictions_total" in text
    assert "fraud_score_bucket" in text


def test_background_retry_loads_the_model_once_registry_is_back(predictor) -> None:
    loader = StaticLoader(predictor)
    loader.fail = True
    settings = Settings(model_retry_seconds=0.05)
    with TestClient(create_app(settings, loader)) as client:
        loader.fail = False
        deadline = time.monotonic() + 5
        while not client.get("/health").json()["model_loaded"] and time.monotonic() < deadline:
            time.sleep(0.05)
        assert client.get("/model").json()["version"] == "1"
