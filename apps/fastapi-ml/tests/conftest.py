import json
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from xgboost import XGBClassifier

from app.core.config import Settings
from app.inference.model import FEATURES, V_FEATURES, LoadedModel

CONTRACTS = Path(__file__).resolve().parents[3] / "libs" / "contracts"


def synthetic_frame(rows: int = 3_000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(rng.standard_normal((rows, 28)), columns=V_FEATURES)
    frame["amount"] = rng.lognormal(3, 1.2, rows)
    frame["label"] = (rng.random(rows) < 0.05).astype(int)
    frame.loc[frame["label"] == 1, ["v14", "v12"]] -= 4.0
    return frame


@pytest.fixture(scope="session")
def predictor() -> XGBClassifier:
    frame = synthetic_frame()
    model = XGBClassifier(n_estimators=30, max_depth=3, learning_rate=0.3)
    return model.fit(frame[FEATURES], frame["label"])


class StaticLoader:
    def __init__(self, predictor, versions: list[str] | None = None) -> None:
        self.predictor = predictor
        self.versions = list(versions or ["1"])
        self.calls = 0
        self.fail = False

    def load(self, name: str, alias: str) -> LoadedModel:
        self.calls += 1
        if self.fail or not self.versions:
            raise ConnectionError("registry unreachable")
        version = self.versions.pop(0) if len(self.versions) > 1 else self.versions[0]
        return LoadedModel(name=name, version=version, alias=alias, predictor=self.predictor)


@pytest.fixture(autouse=True)
def no_default_prediction_log(monkeypatch) -> None:
    monkeypatch.setenv("PREDICTION_LOG_ENABLED", "false")


@pytest.fixture
def settings() -> Settings:
    return Settings(model_name="fraud-xgb", mlflow_tracking_uri="sqlite:///unused.db")


@pytest.fixture
def loader(predictor) -> StaticLoader:
    return StaticLoader(predictor, ["1", "2"])


@pytest.fixture
def client(settings, loader):
    from app.main import create_app

    with TestClient(create_app(settings, loader)) as test_client:
        yield test_client


def transaction_payload(fraud: bool = False) -> dict:
    features = {name: 0.1 for name in V_FEATURES}
    if fraud:
        features |= {"v14": -6.0, "v12": -6.0}
    return {
        "transaction_id": str(uuid.uuid4()),
        "timestamp": "2026-10-26T09:15:00Z",
        "amount": 42.5,
        "features": features,
    }


RAW_EXAMPLE = (CONTRACTS / "examples" / "transaction.raw.v1.json").read_text()


def raw(**overrides) -> bytes:
    payload = json.loads(RAW_EXAMPLE) | {"transaction_id": str(uuid.uuid4())} | overrides
    return json.dumps(payload).encode()
