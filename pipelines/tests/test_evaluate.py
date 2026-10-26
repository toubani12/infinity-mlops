import time

import numpy as np
import pytest

from training.evaluate import compare, p95_latency_ms, pr_auc, recall_at_precision, roc_auc

CHAMPION = {"pr_auc": 0.82, "recall_at_p90": 0.70, "roc_auc": 0.97, "p95_latency_ms": 5.0}


def test_perfect_ranking() -> None:
    y = np.array([0, 0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    assert pr_auc(y, scores) == pytest.approx(1.0)
    assert roc_auc(y, scores) == pytest.approx(1.0)
    assert recall_at_precision(y, scores, 0.9) == pytest.approx(1.0)


def test_recall_at_precision_picks_best_recall_above_target() -> None:
    y = np.array([1, 1, 0, 1, 0, 0, 0, 1])
    scores = np.array([0.95, 0.9, 0.85, 0.8, 0.5, 0.4, 0.3, 0.2])
    assert recall_at_precision(y, scores, 0.9) == pytest.approx(0.5)
    assert recall_at_precision(y, scores, 0.7) == pytest.approx(0.75)


def test_recall_is_zero_when_precision_is_unreachable() -> None:
    y = np.array([0, 1])
    assert recall_at_precision(y, np.array([0.9, 0.1]), 1.01) == 0.0


def test_p95_latency_measures_single_rows(frame) -> None:
    calls = []

    def slow(rows):
        calls.append(len(rows))
        time.sleep(0.002)

    latency = p95_latency_ms(slow, frame, samples=10)
    assert calls == [1] * 10
    assert latency >= 2.0


def test_gate_accepts_first_model_without_champion() -> None:
    result = compare(None, CHAMPION)
    assert result.passed
    assert result.reasons == ["p95_latency_ms 5.00 < 50", "no champion to compare with"]


def test_gate_rejects_first_model_over_latency_budget() -> None:
    result = compare(None, CHAMPION | {"p95_latency_ms": 75.0})
    assert not result.passed
    assert result.summary() == "p95_latency_ms 75.00 is not under 50; no champion to compare with"


def test_gate_accepts_better_pr_auc_with_equal_recall() -> None:
    result = compare(CHAMPION, CHAMPION | {"pr_auc": 0.85})
    assert result.passed
    assert result.reasons == [
        "p95_latency_ms 5.00 < 50",
        "pr_auc 0.8500 > champion 0.8200",
        "recall_at_p90 0.7000 >= champion 0.7000",
    ]


def test_gate_rejects_a_challenger_that_only_ties() -> None:
    result = compare(CHAMPION, CHAMPION)
    assert not result.passed
    assert "pr_auc 0.8200 is not above champion 0.8200" in result.reasons


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"pr_auc": 0.80}, "pr_auc 0.8000 is not above champion 0.8200"),
        ({"pr_auc": 0.90, "recall_at_p90": 0.65}, "recall_at_p90 0.6500 is below champion 0.7000"),
    ],
)
def test_gate_rejects_worse_challenger(change, reason) -> None:
    result = compare(CHAMPION, CHAMPION | change)
    assert not result.passed
    assert reason in result.reasons


def test_gate_rejects_on_latency_even_when_metrics_improve() -> None:
    result = compare(CHAMPION, CHAMPION | {"pr_auc": 0.9, "p95_latency_ms": 50.0})
    assert not result.passed
    assert result.reasons[0] == "p95_latency_ms 50.00 is not under 50"
    assert "pr_auc 0.9000 > champion 0.8200" in result.reasons


def test_gate_lists_every_failure() -> None:
    worse = {"pr_auc": 0.5, "recall_at_p90": 0.1, "roc_auc": 0.9, "p95_latency_ms": 60.0}
    result = compare(CHAMPION, worse)
    assert not result.passed
    assert result.reasons == [
        "p95_latency_ms 60.00 is not under 50",
        "pr_auc 0.5000 is not above champion 0.8200",
        "recall_at_p90 0.1000 is below champion 0.7000",
    ]


def test_gate_latency_budget_is_configurable() -> None:
    better = CHAMPION | {"pr_auc": 0.85}
    assert compare(CHAMPION, better).passed
    assert not compare(CHAMPION, better, max_p95_ms=5.0).passed
