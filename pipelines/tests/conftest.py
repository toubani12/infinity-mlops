import pandas as pd
import pytest

from data.ingest import normalize_columns
from data.synthetic import generate


@pytest.fixture(scope="session")
def raw_frame() -> pd.DataFrame:
    return normalize_columns(generate(rows=4_000, fraud_rate=0.03, seed=7))


@pytest.fixture
def frame(raw_frame: pd.DataFrame) -> pd.DataFrame:
    return raw_frame.copy()


@pytest.fixture(scope="session")
def tracking(tmp_path_factory: pytest.TempPathFactory) -> str:
    import mlflow

    root = tmp_path_factory.mktemp("mlflow")
    uri = f"sqlite:///{root / 'mlflow.db'}"
    mlflow.set_tracking_uri(uri)
    mlflow.create_experiment("fraud-xgb-test", artifact_location=(root / "artifacts").as_uri())
    return uri
