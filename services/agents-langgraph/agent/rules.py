from agent.config import Settings
from agent.state import GateResult, Qualification
from agent.tools import Evaluation
from agent.tools.report import DriftReport

COMPARED_METRICS = ("pr_auc", "recall_at_p90")


def qualify_report(report: DriftReport, settings: Settings) -> tuple[Qualification, list[str]]:
    if report.missing_features or report.out_of_range_share > settings.out_of_range_threshold:
        reasons = []
        if report.missing_features:
            reasons.append(f"missing features: {', '.join(report.missing_features)}")
        if report.out_of_range_share > settings.out_of_range_threshold:
            reasons.append(
                f"out of range share {report.out_of_range_share:.2f}"
                f" > {settings.out_of_range_threshold:.2f}"
            )
        return "data_incident", reasons

    drift_share = f"drift share {report.drift_share:.2f}"
    pr_auc_drop = f"pr_auc drop {report.pr_auc_drop:.3f}"
    drifting = report.drift_share > settings.drift_share_threshold
    degrading = report.pr_auc_drop > settings.pr_auc_drop_threshold
    if not drifting and not degrading:
        return "noise", [
            f"{drift_share} <= {settings.drift_share_threshold:.2f}",
            f"{pr_auc_drop} <= {settings.pr_auc_drop_threshold:.3f}",
        ]
    reasons = []
    if drifting:
        reasons.append(f"{drift_share} > {settings.drift_share_threshold:.2f}")
    if degrading:
        reasons.append(f"{pr_auc_drop} > {settings.pr_auc_drop_threshold:.3f}")
    return "real_drift", reasons


def evaluate_gate(evaluation: Evaluation, max_p95_latency_ms: float) -> GateResult:
    """Recheck the training gate: the agent never promotes on the training job's word alone."""
    challenger = evaluation["challenger"]
    champion = evaluation["champion"]
    failures: list[str] = []
    passes: list[str] = []

    if not evaluation["gate_passed"]:
        failures.append(f"training gate failed: {evaluation['gate_reasons'] or 'no reason given'}")

    for metric in COMPARED_METRICS:
        value = challenger.get(metric)
        reference = champion.get(metric) if champion else None
        if value is None:
            failures.append(f"challenger has no {metric}")
        elif reference is None:
            passes.append(f"no champion {metric} to compare, challenger {value:.3f}")
        elif value > reference:
            passes.append(f"{metric} {value:.3f} > champion {reference:.3f}")
        else:
            failures.append(f"{metric} {value:.3f} <= champion {reference:.3f}")

    latency = challenger.get("p95_latency_ms")
    if latency is None:
        failures.append("challenger has no p95_latency_ms")
    elif latency >= max_p95_latency_ms:
        failures.append(f"p95 latency {latency:.1f} ms >= {max_p95_latency_ms:.0f} ms")
    else:
        passes.append(f"p95 latency {latency:.1f} ms < {max_p95_latency_ms:.0f} ms")

    if failures:
        return {"passed": False, "reasons": failures}
    return {"passed": True, "reasons": passes}
