import numpy as np

from training.threshold import DEFAULT_THRESHOLD, choose_threshold


def test_threshold_keeps_precision_and_maximises_recall() -> None:
    y = np.array([0, 0, 0, 0, 1, 0, 1, 1, 1, 1])
    scores = np.array([0.05, 0.1, 0.2, 0.3, 0.35, 0.4, 0.6, 0.7, 0.8, 0.9])
    threshold = choose_threshold(y, scores, min_precision=0.9)
    flagged = scores >= threshold
    assert y[flagged].mean() >= 0.9
    assert threshold == 0.6


def test_threshold_falls_back_when_precision_unreachable() -> None:
    y = np.array([1, 0, 1, 0])
    scores = np.array([0.1, 0.9, 0.2, 0.8])
    assert choose_threshold(y, scores) == DEFAULT_THRESHOLD
