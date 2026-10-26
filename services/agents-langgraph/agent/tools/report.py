from pydantic import BaseModel, Field, ValidationError


class InvalidReport(ValueError):
    pass


class DriftWindow(BaseModel):
    start: str
    end: str
    rows: int = Field(ge=0)


class DriftMetrics(BaseModel):
    pr_auc: float | None = None
    reference_pr_auc: float | None = None
    recall_at_p90: float | None = None
    labeled_rows: int | None = None


class DriftReport(BaseModel):
    report_id: str
    detected_at: str
    window: DriftWindow
    drift_share: float = Field(ge=0, le=1)
    drifted_features: list[str]
    missing_features: list[str] = []
    out_of_range_share: float = Field(default=0.0, ge=0, le=1)
    metrics: DriftMetrics
    model_version: str | None = None
    report_uri: str | None = None

    @property
    def pr_auc_drop(self) -> float:
        if self.metrics.pr_auc is None or self.metrics.reference_pr_auc is None:
            return 0.0
        return self.metrics.reference_pr_auc - self.metrics.pr_auc


class PayloadReportReader:
    """read_report: the drift.detected message carries the whole summary the agent decides on."""

    def read(self, payload: dict) -> DriftReport:
        try:
            return DriftReport.model_validate(payload)
        except ValidationError as exc:
            raise InvalidReport(str(exc)) from exc
