import asyncio

import numpy as np
import pytest

from app.core.config import Settings
from app.inference.model import LoadedModel
from app.inference.service import DEFAULT_THRESHOLD, InferenceService


class ConstantPredictor:
    def __init__(self, score: float) -> None:
        self.score = score

    def predict_proba(self, frame):
        return np.column_stack(
            [1 - np.full(len(frame), self.score), np.full(len(frame), self.score)]
        )


class StaticLoader:
    def __init__(self, threshold: float | None) -> None:
        self.threshold = threshold

    def load(self, name: str, alias: str) -> LoadedModel:
        return LoadedModel(name, "7", alias, ConstantPredictor(0.4), threshold=self.threshold)


def test_auto_threshold_is_parsed() -> None:
    assert Settings(fraud_threshold="auto").fraud_threshold == "auto"
    assert Settings(fraud_threshold="0.3").fraud_threshold == 0.3
    with pytest.raises(ValueError):
        Settings(fraud_threshold="1.5")


@pytest.mark.parametrize(
    ("fixed", "tagged", "expected"),
    [(None, 0.35, 0.35), (None, None, DEFAULT_THRESHOLD), (0.8, 0.35, 0.8)],
)
def test_threshold_source(fixed, tagged, expected) -> None:
    service = InferenceService(StaticLoader(tagged), "fraud-xgb", "champion", fixed)
    asyncio.run(service.reload())
    assert service.threshold == expected
