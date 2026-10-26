import numpy as np
import pytest

from data.synthetic import generate, main


def test_schema_and_fraud_count() -> None:
    frame = generate(rows=10_000, fraud_rate=0.01, seed=1)
    assert list(frame.columns) == ["Time", *[f"V{i}" for i in range(1, 29)], "Amount", "Class"]
    assert len(frame) == 10_000
    assert frame["Class"].sum() == 100
    assert frame["Time"].is_monotonic_increasing
    assert frame["Time"].between(0, 2 * 86_400).all()
    assert (frame["Amount"] >= 0).all()


def test_frauds_are_shifted_on_discriminant_features() -> None:
    frame = generate(rows=20_000, fraud_rate=0.05, seed=2)
    means = frame.groupby("Class")[["V14", "V12", "V10", "V4", "V17", "V20"]].mean()
    assert means.loc[1, "V14"] < means.loc[0, "V14"] - 3
    assert means.loc[1, "V4"] > means.loc[0, "V4"] + 2
    assert abs(means.loc[1, "V20"] - means.loc[0, "V20"]) < 0.2


def test_same_seed_is_reproducible() -> None:
    assert generate(rows=500, seed=3).equals(generate(rows=500, seed=3))
    assert not generate(rows=500, seed=3).equals(generate(rows=500, seed=4))


def test_amount_is_heavy_tailed() -> None:
    amount = generate(rows=20_000, seed=5)["Amount"]
    assert amount.mean() > 2 * amount.median()
    assert np.log1p(amount).std() > 1


def test_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        generate(rows=0)
    with pytest.raises(ValueError):
        generate(rows=10, fraud_rate=1.5)


def test_cli_writes_csv_and_parquet(tmp_path) -> None:
    main(["--rows", "200", "--fraud-rate", "0.05", "--out", str(tmp_path / "s.csv")])
    main(["--rows", "200", "--out", str(tmp_path / "s.parquet")])
    assert (tmp_path / "s.csv").read_text().startswith("Time,V1,")
    assert (tmp_path / "s.parquet").stat().st_size > 0
