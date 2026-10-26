import numpy as np
import pandas as pd
import pytest

from training.features import FEATURES, select_window, time_stratified_split, xy


def test_feature_order_matches_conventions() -> None:
    assert FEATURES == [f"v{i}" for i in range(1, 29)] + ["amount"]


def test_split_keeps_time_order_per_class_and_test_after_train(frame) -> None:
    split = time_stratified_split(frame.sample(frac=1, random_state=1))
    assert sum(len(p) for p in split.parts().values()) == len(frame)
    assert split.train["time"].max() < split.test["time"].min()
    for label in (0, 1):
        train, valid, test = (p[p["class"] == label]["time"] for p in split.parts().values())
        assert train.max() <= valid.min() and valid.max() <= test.min()


def test_split_keeps_fraud_ratio(frame) -> None:
    summary = time_stratified_split(frame).summary()
    for part in summary.values():
        assert part["fraud_rate"] == pytest.approx(0.03, abs=0.001)
    assert [summary[p]["rows"] for p in ("train", "valid", "test")] == [2_800, 600, 600]


def test_split_keeps_ratio_when_frauds_cluster_in_time() -> None:
    rows = 2_000
    labels = np.zeros(rows, dtype=int)
    labels[np.arange(0, rows, 25)] = 1
    labels[1_380:1_420] = 1
    frame = pd.DataFrame({"time": np.arange(rows, dtype=float), "class": labels})
    split = time_stratified_split(frame)
    rates = [p["class"].mean() for p in split.parts().values()]
    assert max(rates) - min(rates) < 0.002


def test_split_refuses_train_rows_inside_test_period() -> None:
    labels = np.r_[np.zeros(900, dtype=int), np.ones(100, dtype=int)]
    frame = pd.DataFrame({"time": np.arange(1_000, dtype=float), "class": labels})
    with pytest.raises(ValueError, match="overlap"):
        time_stratified_split(frame)


def test_split_rejects_bad_fractions(frame) -> None:
    with pytest.raises(ValueError):
        time_stratified_split(frame, fractions=(0.5, 0.5, 0.5))
    with pytest.raises(ValueError):
        time_stratified_split(frame.iloc[:2])


def test_select_window(frame) -> None:
    last_day = select_window(frame, 1)
    assert last_day["time"].min() >= frame["time"].max() - 86_400
    assert len(select_window(frame, None)) == len(frame)
    with pytest.raises(ValueError):
        select_window(frame, 0)


def test_xy(frame) -> None:
    x, y = xy(frame)
    assert list(x.columns) == FEATURES
    assert y.name == "class"
