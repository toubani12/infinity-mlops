"""Synthetic stand-in for the ULB credit card dataset, same columns and casing as the CSV."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REAL_ROWS = 284_807
REAL_FRAUD_RATE = 492 / REAL_ROWS
HORIZON_HOURS = 48

# Standard deviations of the PCA components decrease with their rank, as in the real data.
V_STD = np.linspace(1.95, 0.33, 28)

# Mean of the fraud class on the most discriminant components of the real dataset.
FRAUD_SHIFT = {
    "V14": -6.9,
    "V12": -6.2,
    "V10": -5.6,
    "V17": -6.6,
    "V4": 4.5,
    "V11": 3.8,
    "V3": -7.0,
    "V16": -4.1,
}

# Relative transaction volume per hour of day; the real data has a deep night trough.
HOURLY_VOLUME = np.array(
    [0.35, 0.2, 0.12, 0.1, 0.08, 0.12, 0.2, 0.35, 0.6, 0.85, 0.95, 1.0]
    + [1.0, 0.95, 0.95, 0.95, 0.95, 0.95, 1.0, 1.0, 0.9, 0.8, 0.7, 0.5]
)


def _times(rng: np.random.Generator, n: int, hourly: np.ndarray) -> np.ndarray:
    weights = np.tile(hourly, HORIZON_HOURS // 24)
    hours = rng.choice(HORIZON_HOURS, size=n, p=weights / weights.sum())
    return np.floor((hours + rng.random(n)) * 3600.0)


def _legit_amounts(rng: np.random.Generator, n: int) -> np.ndarray:
    amounts = rng.lognormal(mean=3.0, sigma=1.5, size=n)
    amounts[rng.random(n) < 0.006] = 0.0
    return amounts


def _fraud_amounts(rng: np.random.Generator, n: int) -> np.ndarray:
    small = rng.random(n) < 0.4
    return np.where(small, rng.lognormal(0.3, 0.6, size=n), rng.lognormal(4.0, 1.4, size=n))


def _fraud_strength(rng: np.random.Generator, n: int) -> np.ndarray:
    # A share of frauds mimics legitimate behaviour; this is what keeps PR-AUC below 0.9.
    camouflaged = rng.random(n) < 0.22
    return np.where(camouflaged, rng.uniform(0.0, 0.12, size=n), 0.15 + rng.beta(2, 2, size=n))


def generate(
    rows: int = REAL_ROWS, fraud_rate: float = REAL_FRAUD_RATE, seed: int = 42
) -> pd.DataFrame:
    if rows <= 0 or not 0 <= fraud_rate < 1:
        raise ValueError("rows must be positive and fraud_rate in [0, 1)")
    rng = np.random.default_rng(seed)
    frauds = int(round(rows * fraud_rate))
    legit = rows - frauds

    v = rng.standard_normal((rows, 28)) * V_STD
    v[legit:] *= 1.6
    strength = _fraud_strength(rng, frauds)
    for name, shift in FRAUD_SHIFT.items():
        col = int(name[1:]) - 1
        v[legit:, col] += strength * shift

    frame = pd.DataFrame(v, columns=[f"V{i}" for i in range(1, 29)])
    frame.insert(
        0,
        "Time",
        np.concatenate(
            [_times(rng, legit, HOURLY_VOLUME), _times(rng, frauds, np.sqrt(HOURLY_VOLUME))]
        ),
    )
    amounts = np.concatenate([_legit_amounts(rng, legit), _fraud_amounts(rng, frauds)])
    frame["Amount"] = np.round(np.clip(amounts, 0.0, 25_691.16), 2)
    frame["Class"] = np.r_[np.zeros(legit, dtype=np.int64), np.ones(frauds, dtype=np.int64)]
    return frame.sort_values("Time", kind="stable").reset_index(drop=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic credit card dataset")
    parser.add_argument("--rows", type=int, default=REAL_ROWS)
    parser.add_argument("--fraud-rate", type=float, default=REAL_FRAUD_RATE)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True, help=".csv or .parquet")
    args = parser.parse_args(argv)

    frame = generate(args.rows, args.fraud_rate, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.suffix == ".parquet":
        frame.to_parquet(args.out, index=False)
    else:
        frame.to_csv(args.out, index=False)
    print(f"wrote {len(frame)} rows, {int(frame['Class'].sum())} frauds to {args.out}")


if __name__ == "__main__":
    main()
