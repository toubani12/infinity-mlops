from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FEATURES = [*(f"v{i}" for i in range(1, 29)), "amount"]
CONTRACTS = Path(__file__).resolve().parents[3] / "libs" / "contracts"
NOW = datetime(2026, 10, 26, 10, 20, tzinfo=UTC)


def frame(
    rows: int = 2_000,
    seed: int = 0,
    shift: dict[str, float] | None = None,
    informative: bool = True,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = pd.DataFrame(rng.standard_normal((rows, len(FEATURES))), columns=FEATURES)
    data["amount"] = rng.lognormal(3, 1, rows)
    labels = (rng.random(rows) < 0.05).astype(int)
    noise = rng.random(rows)
    data["fraud_score"] = np.clip(0.7 * labels + 0.3 * noise, 0, 1) if informative else noise
    data["label"] = pd.array(labels, dtype="Int64")
    data["model_version"] = "3"
    for feature, delta in (shift or {}).items():
        data[feature] += delta
    return data


def write_partition(root: Path, data: pd.DataFrame, hour: datetime, name: str = "part-a") -> Path:
    path = root / f"dt={hour:%Y-%m-%d}" / f"hour={hour:%H}" / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(path, index=False)
    return path


@pytest.fixture(autouse=True)
def no_telemetry(monkeypatch) -> None:
    monkeypatch.setenv("DO_NOT_TRACK", "1")


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)
