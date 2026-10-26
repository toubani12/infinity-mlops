import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

GATE_METRICS = ("pr_auc", "recall_at_p90")


@dataclass(frozen=True)
class Metrics:
    pr_auc: float
    recall_at_p90: float
    roc_auc: float
    p95_latency_ms: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def pr_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    return float(average_precision_score(y_true, scores))


def recall_at_precision(y_true: np.ndarray, scores: np.ndarray, precision: float = 0.9) -> float:
    precisions, recalls, _ = precision_recall_curve(y_true, scores)
    reachable = recalls[precisions >= precision]
    return float(reachable.max()) if reachable.size else 0.0


def roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    return float(roc_auc_score(y_true, scores))


def p95_latency_ms(
    predict: Callable[[pd.DataFrame], object], rows: pd.DataFrame, samples: int = 200
) -> float:
    durations = []
    for position in range(min(samples, len(rows))):
        row = rows.iloc[[position]]
        start = time.perf_counter()
        predict(row)
        durations.append((time.perf_counter() - start) * 1000.0)
    return float(np.percentile(durations, 95)) if durations else 0.0


def evaluate(model, features: pd.DataFrame, labels: pd.Series, samples: int = 200) -> Metrics:
    scores = model.predict_proba(features)[:, 1]
    y_true = labels.to_numpy()
    return Metrics(
        pr_auc=pr_auc(y_true, scores),
        recall_at_p90=recall_at_precision(y_true, scores, 0.9),
        roc_auc=roc_auc(y_true, scores),
        p95_latency_ms=p95_latency_ms(model.predict_proba, features, samples),
    )


def compare(
    champion_metrics: Mapping[str, float] | None,
    challenger_metrics: Mapping[str, float],
    max_p95_ms: float = 50.0,
) -> GateResult:
    """The challenger wins only if it matches or beats the champion on PR-AUC and recall at
    90 % precision, and its single-row p95 latency stays under the budget."""
    reasons: list[str] = []
    passed = True
    latency = challenger_metrics["p95_latency_ms"]
    if latency >= max_p95_ms:
        passed = False
        reasons.append(f"p95_latency_ms {latency:.2f} is not under {max_p95_ms:.0f}")
    else:
        reasons.append(f"p95_latency_ms {latency:.2f} < {max_p95_ms:.0f}")
    if champion_metrics is None:
        reasons.append("no champion to compare with")
        return GateResult(passed, reasons)
    for metric in GATE_METRICS:
        challenger, champion = challenger_metrics[metric], champion_metrics[metric]
        if challenger < champion:
            passed = False
            reasons.append(f"{metric} {challenger:.4f} is below champion {champion:.4f}")
        else:
            reasons.append(f"{metric} {challenger:.4f} >= champion {champion:.4f}")
    return GateResult(passed, reasons)
