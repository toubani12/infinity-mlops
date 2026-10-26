import pytest

from monitor.thresholds import Signals, Thresholds, decide


def signals(**overrides) -> Signals:
    base = dict(
        drift_share=0.1,
        drifted_features=[],
        missing_features=[],
        out_of_range_share=0.0,
        pr_auc=0.84,
        reference_pr_auc=0.85,
    )
    return Signals(**(base | overrides))


def test_quiet_window_is_not_published() -> None:
    decision = decide(signals(), Thresholds())
    assert not decision.publish and decision.reasons == []


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"drift_share": 0.31}, "drift share 0.31 > 0.30"),
        ({"pr_auc": 0.79}, "pr-auc dropped by 0.060 > 0.050"),
        ({"missing_features": ["v3"]}, "missing features: v3"),
        ({"out_of_range_share": 0.2}, "out-of-range share 0.200 > 0.050"),
    ],
)
def test_each_signal_triggers(overrides, reason) -> None:
    decision = decide(signals(**overrides), Thresholds())
    assert decision.publish and decision.reasons == [reason]


def test_share_at_threshold_and_unknown_pr_auc_do_not_trigger() -> None:
    assert not decide(signals(drift_share=0.3, pr_auc=None), Thresholds()).publish


def test_thresholds_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("DRIFT_SHARE_THRESHOLD", "0.5")
    monkeypatch.setenv("PR_AUC_DROP_THRESHOLD", "0.1")
    thresholds = Thresholds()
    assert (thresholds.drift_share, thresholds.pr_auc_drop) == (0.5, 0.1)
    assert not decide(signals(drift_share=0.4), thresholds).publish
