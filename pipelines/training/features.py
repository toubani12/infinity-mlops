from dataclasses import dataclass

import numpy as np
import pandas as pd

from data.schema import FEATURES, SECONDS_PER_DAY, TARGET, TIME

__all__ = ["FEATURES", "Split", "select_window", "split_newest", "time_stratified_split", "xy"]


@dataclass(frozen=True)
class Split:
    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame

    def summary(self) -> dict[str, dict[str, float]]:
        return {name: _describe(part) for name, part in self.parts().items()}

    def parts(self) -> dict[str, pd.DataFrame]:
        return {"train": self.train, "valid": self.valid, "test": self.test}


def _describe(part: pd.DataFrame) -> dict[str, float]:
    return {
        "rows": len(part),
        "frauds": int(part[TARGET].sum()),
        "fraud_rate": float(part[TARGET].mean()) if len(part) else 0.0,
        "time_start": float(part[TIME].min()) if len(part) else float("nan"),
        "time_end": float(part[TIME].max()) if len(part) else float("nan"),
    }


def xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    return df[FEATURES], df[TARGET]


def select_window(df: pd.DataFrame, days: float | None) -> pd.DataFrame:
    if days is None:
        return df
    if days <= 0:
        raise ValueError("window must be positive")
    cutoff = df[TIME].max() - days * SECONDS_PER_DAY
    return df[df[TIME] >= cutoff]


def time_stratified_split(
    df: pd.DataFrame, fractions: tuple[float, float, float] = (0.7, 0.15, 0.15)
) -> Split:
    """Cut each class at its own time quantiles, so every block keeps the global fraud rate,
    and refuse splits where training rows reach into the test period."""
    if len(fractions) != 3 or not np.isclose(sum(fractions), 1.0) or min(fractions) <= 0:
        raise ValueError("fractions must be three positive shares summing to 1")
    if len(df) < 3:
        raise ValueError("need at least 3 rows to split")
    blocks: dict[str, list[pd.DataFrame]] = {"train": [], "valid": [], "test": []}
    for _, group in df.sort_values(TIME, kind="stable").groupby(TARGET, sort=True):
        first = round(len(group) * fractions[0])
        second = round(len(group) * (fractions[0] + fractions[1]))
        blocks["train"].append(group.iloc[:first])
        blocks["valid"].append(group.iloc[first:second])
        blocks["test"].append(group.iloc[second:])
    train, valid, test = (
        pd.concat(parts).sort_values(TIME, kind="stable").reset_index(drop=True)
        for parts in blocks.values()
    )
    if len(train) and len(test) and train[TIME].max() >= test[TIME].min():
        raise ValueError("training rows overlap the test period, frauds are too unevenly timed")
    return Split(train, valid, test)


def split_newest(df: pd.DataFrame, share: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Older and newest rows, cut per class at its own time quantile like the main split."""
    if not 0 < share < 1:
        raise ValueError("share must be in (0, 1)")
    older: list[pd.DataFrame] = []
    newest: list[pd.DataFrame] = []
    for _, group in df.sort_values(TIME, kind="stable").groupby(TARGET, sort=True):
        cut = round(len(group) * (1 - share))
        older.append(group.iloc[:cut])
        newest.append(group.iloc[cut:])
    return _stack(older), _stack(newest)


def _stack(parts: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(parts).sort_values(TIME, kind="stable").reset_index(drop=True)
