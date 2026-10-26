import pytest

from agent.config import Settings
from agent.rules import evaluate_gate, qualify_report
from agent.tools.report import DriftReport, InvalidReport, PayloadReportReader
from tests.fakes import metrics

SETTINGS = Settings(_env_file=None)


def report(drift_report: dict, **changes) -> DriftReport:
    payload = drift_report | changes
    return PayloadReportReader().read(payload)


def test_missing_features_is_a_data_incident(drift_report):
    qualification, reasons = qualify_report(
        report(drift_report, missing_features=["v14"]), SETTINGS
    )
    assert qualification == "data_incident"
    assert reasons == ["missing features: v14"]


def test_out_of_range_values_are_a_data_incident(drift_report):
    qualification, reasons = qualify_report(report(drift_report, out_of_range_share=0.08), SETTINGS)
    assert qualification == "data_incident"
    assert reasons == ["out of range share 0.08 > 0.05"]


def test_drift_share_above_threshold_is_real_drift(drift_report):
    metrics_without_drop = {"pr_auc": 0.84, "reference_pr_auc": 0.84}
    qualification, reasons = qualify_report(
        report(drift_report, drift_share=0.36, metrics=metrics_without_drop), SETTINGS
    )
    assert qualification == "real_drift"
    assert reasons == ["drift share 0.36 > 0.30"]


def test_pr_auc_drop_alone_is_real_drift(drift_report):
    qualification, reasons = qualify_report(report(drift_report, drift_share=0.1), SETTINGS)
    assert qualification == "real_drift"
    assert reasons == ["pr_auc drop 0.130 > 0.050"]


def test_small_drift_without_degradation_is_noise(drift_report):
    small = {"pr_auc": 0.82, "reference_pr_auc": 0.84, "labeled_rows": 40}
    qualification, _ = qualify_report(
        report(drift_report, drift_share=0.2, metrics=small), SETTINGS
    )
    assert qualification == "noise"


def test_unknown_pr_auc_counts_as_no_drop(drift_report):
    unlabeled = {"pr_auc": None, "reference_pr_auc": 0.84}
    parsed = report(drift_report, drift_share=0.2, metrics=unlabeled)
    assert parsed.pr_auc_drop == 0.0
    assert qualify_report(parsed, SETTINGS)[0] == "noise"


def test_thresholds_come_from_settings(drift_report):
    strict = Settings(_env_file=None, drift_share_threshold=0.1, pr_auc_drop_threshold=0.5)
    flat = {"pr_auc": 0.84, "reference_pr_auc": 0.84}
    assert qualify_report(report(drift_report, drift_share=0.2, metrics=flat), strict)[0] == (
        "real_drift"
    )


def test_invalid_payload_is_rejected(drift_report):
    with pytest.raises(InvalidReport):
        PayloadReportReader().read(drift_report | {"drift_share": 3})


def evaluation(challenger, champion, gate_passed=True):
    return {
        "challenger": challenger,
        "champion": champion,
        "gate_passed": gate_passed,
        "gate_reasons": "" if gate_passed else "pr_auc not better",
    }


def test_gate_passes_when_challenger_beats_champion():
    gate = evaluate_gate(
        evaluation(metrics("4", 0.83, 0.68, 6.4), metrics("3", 0.71, 0.52, 6.1)), 50
    )
    assert gate == {
        "passed": True,
        "reasons": [
            "pr_auc 0.830 > champion 0.710",
            "recall_at_p90 0.680 > champion 0.520",
            "p95 latency 6.4 ms < 50 ms",
        ],
    }


def test_gate_fails_on_worse_recall_and_slow_latency():
    gate = evaluate_gate(
        evaluation(metrics("4", 0.83, 0.50, 75.0), metrics("3", 0.71, 0.52, 6.1)), 50
    )
    assert not gate["passed"]
    assert gate["reasons"] == [
        "recall_at_p90 0.500 <= champion 0.520",
        "p95 latency 75.0 ms >= 50 ms",
    ]


def test_gate_respects_the_training_job_verdict():
    gate = evaluate_gate(
        evaluation(metrics("4", 0.83, 0.68, 6.4), metrics("3", 0.71, 0.52, 6.1), False), 50
    )
    assert gate == {"passed": False, "reasons": ["training gate failed: pr_auc not better"]}


def test_gate_without_champion_checks_latency_and_presence():
    challenger = metrics("1", 0.8, 0.6, 5.0) | {"recall_at_p90": None}
    gate = evaluate_gate(evaluation(challenger, None), 50)
    assert gate == {"passed": False, "reasons": ["challenger has no recall_at_p90"]}
    first_model = evaluate_gate(evaluation(metrics("1", 0.8, 0.6, 5.0), None), 50)
    assert first_model["passed"]
