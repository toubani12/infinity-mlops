from dataclasses import dataclass, field

from pydantic import Field
from pydantic_settings import BaseSettings


class Thresholds(BaseSettings):
    drift_share: float = Field(default=0.3, ge=0, le=1, alias="DRIFT_SHARE_THRESHOLD")
    pr_auc_drop: float = Field(default=0.05, ge=0, le=1, alias="PR_AUC_DROP_THRESHOLD")
    out_of_range_share: float = Field(default=0.05, ge=0, le=1, alias="OUT_OF_RANGE_THRESHOLD")
    range_margin: float = Field(default=0.1, ge=0, alias="RANGE_MARGIN")
    min_labeled_rows: int = Field(default=200, ge=1, alias="MIN_LABELED_ROWS")
    min_labeled_frauds: int = Field(default=5, ge=1, alias="MIN_LABELED_FRAUDS")

    model_config = {"populate_by_name": True, "extra": "ignore"}


@dataclass(frozen=True)
class Signals:
    drift_share: float
    drifted_features: list[str]
    missing_features: list[str]
    out_of_range_share: float
    pr_auc: float | None
    reference_pr_auc: float | None


@dataclass(frozen=True)
class Decision:
    publish: bool
    reasons: list[str] = field(default_factory=list)


def decide(signals: Signals, thresholds: Thresholds) -> Decision:
    reasons = []
    if signals.drift_share > thresholds.drift_share:
        reasons.append(f"drift share {signals.drift_share:.2f} > {thresholds.drift_share:.2f}")
    if signals.pr_auc is not None and signals.reference_pr_auc is not None:
        drop = signals.reference_pr_auc - signals.pr_auc
        if drop > thresholds.pr_auc_drop:
            reasons.append(f"pr-auc dropped by {drop:.3f} > {thresholds.pr_auc_drop:.3f}")
    if signals.missing_features:
        reasons.append(f"missing features: {', '.join(signals.missing_features)}")
    if signals.out_of_range_share > thresholds.out_of_range_share:
        share, limit = signals.out_of_range_share, thresholds.out_of_range_share
        reasons.append(f"out-of-range share {share:.3f} > {limit:.3f}")
    return Decision(bool(reasons), reasons)
