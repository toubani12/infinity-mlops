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
