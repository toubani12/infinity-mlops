import json
import logging
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset
from sklearn.metrics import average_precision_score, precision_recall_curve

from monitor.storage import Storage
from monitor.thresholds import Decision, Signals, Thresholds, decide

log = logging.getLogger(__name__)

FEATURES = [*(f"v{i}" for i in range(1, 29)), "amount"]


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    @classmethod
    def last_hours(cls, end: datetime, hours: int) -> "Window":
        current_hour = end.replace(minute=0, second=0, microsecond=0)
        return cls(current_hour - timedelta(hours=hours - 1), end)

    def partitions(self) -> list[str]:
        hours = int((self.end - self.start) / timedelta(hours=1)) + 1
        return [
            f"dt={hour:%Y-%m-%d}/hour={hour:%H}/"
            for hour in (self.start + timedelta(hours=i) for i in range(hours))
            if hour <= self.end
        ]


@dataclass(frozen=True)
class DriftResult:
    report_id: str
    window: Window
    rows: int
    signals: Signals
    decision: Decision
    recall_at_p90: float | None
    labeled_rows: int
    model_version: str | None
    report_uri: str | None = None


def load_window(storage: Storage, predictions_uri: str, window: Window) -> pd.DataFrame:
    root = predictions_uri.rstrip("/")
    parts = [
        uri
        for partition in window.partitions()
        for uri in storage.list(f"{root}/{partition}")
        if uri.endswith(".parquet")
    ]
    frames = [storage.read_parquet(uri) for uri in parts]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def missing_features(
    current: pd.DataFrame, reference: pd.DataFrame, max_share: float = 0.1
) -> list[str]:
    """A feature is missing when absent, null on more than `max_share` of the rows, or when a
    single value fills more than `max_share` of the rows although it is rare in the reference:
    upstream outages show up as nulls or as a default fill such as 0.0."""
    missing = []
    for feature in FEATURES:
        if feature not in current.columns:
            missing.append(feature)
            continue
        values = current[feature]
        if values.isna().mean() > max_share:
            missing.append(feature)
        elif values.notna().any() and _top_share(values) > max_share:
            if _top_share(reference[feature]) < max_share / 2:
                missing.append(feature)
    return missing


def _top_share(values: pd.Series) -> float:
    return float(values.value_counts(normalize=True, dropna=True).iloc[0])


def out_of_range_share(current: pd.DataFrame, reference: pd.DataFrame, margin: float) -> float:
    present = [f for f in FEATURES if f in current.columns]
    if current.empty or not present:
        return 0.0
    low, high = reference[present].min(), reference[present].max()
    span = high - low
    values = current[present]
    outside = (values < low - margin * span) | (values > high + margin * span)
    if "amount" in present:
        outside["amount"] |= values["amount"] < 0
    return float(outside.any(axis=1).mean())


def label_metrics(
    frame: pd.DataFrame, thresholds: Thresholds
) -> tuple[float | None, float | None, int]:
    if "label" not in frame.columns:
        return None, None, 0
    labeled = frame.dropna(subset=["label", "fraud_score"])
    y_true = labeled["label"].astype(int).to_numpy()
    enough = len(labeled) >= thresholds.min_labeled_rows
    if not enough or y_true.sum() < thresholds.min_labeled_frauds or y_true.sum() == len(y_true):
        return None, None, len(labeled)
    scores = labeled["fraud_score"].to_numpy()
    precision, recall, _ = precision_recall_curve(y_true, scores)
    reachable = recall[precision >= 0.9]
    recall_at_p90 = float(reachable.max()) if reachable.size else 0.0
    return float(average_precision_score(y_true, scores)), recall_at_p90, len(labeled)


def evidently_drift(
    current: pd.DataFrame, reference: pd.DataFrame, drift_share: float, max_rows: int
):
    columns = [f for f in FEATURES if f in current.columns and current[f].notna().any()]
    if not columns:
        return None, columns
    definition = DataDefinition(numerical_columns=columns)
    sample = current.sample(max_rows, random_state=0) if len(current) > max_rows else current
    report = Report([DataDriftPreset(columns=columns, drift_share=drift_share)], include_tests=True)
    snapshot = report.run(
        current_data=Dataset.from_pandas(sample[columns], data_definition=definition),
        reference_data=Dataset.from_pandas(reference[columns], data_definition=definition),
    )
    return snapshot, columns


def drifted_columns(snapshot) -> list[str]:
    drifted: list[str] = []
    if snapshot is None:
        return drifted
    for test in snapshot.dict()["tests"]:
        params = test["metric_config"]["params"]
        if params.get("type", "").endswith("ValueDrift") and test["status"] == "FAIL":
            drifted.append(params["column"])
    return drifted


def report_key(window: Window, report_id: str) -> str:
    return f"{window.end:%Y/%m/%d/%H}/{report_id}"


def analyze(
    current: pd.DataFrame,
    reference: pd.DataFrame,
    window: Window,
    thresholds: Thresholds,
    *,
    storage: Storage | None = None,
    reports_uri: str | None = None,
    max_rows: int = 50_000,
) -> DriftResult:
    report_id = str(uuid.uuid4())
    missing = missing_features(current, reference, thresholds.missing_share)
    snapshot, columns = evidently_drift(
        current.drop(columns=missing, errors="ignore"), reference, thresholds.drift_share, max_rows
    )
    drifted = drifted_columns(snapshot)
    reference_pr_auc, _, _ = label_metrics(reference, thresholds)
    pr_auc, recall_at_p90, labeled_rows = label_metrics(current, thresholds)
    signals = Signals(
        # Missing features count as drifted: the model sees values it was never trained on.
        drift_share=len(set(drifted) | set(missing)) / len(FEATURES),
        drifted_features=sorted(drifted, key=FEATURES.index),
        missing_features=missing,
        out_of_range_share=out_of_range_share(current, reference, thresholds.range_margin),
        pr_auc=pr_auc,
        reference_pr_auc=reference_pr_auc,
    )
    versions = current["model_version"].dropna() if "model_version" in current else pd.Series()
    result = DriftResult(
        report_id=report_id,
        window=window,
        rows=len(current),
        signals=signals,
        decision=decide(signals, thresholds),
        recall_at_p90=recall_at_p90,
        labeled_rows=labeled_rows,
        model_version=str(versions.mode().iloc[0]) if len(versions) else None,
    )
    if storage and reports_uri:
        base = f"{reports_uri.rstrip('/')}/{report_key(window, report_id)}"
        if snapshot is not None:
            html = snapshot.get_html_str(as_iframe=False).encode()
            storage.write_bytes(f"{base}.html", html)
        evidently = snapshot.dict() if snapshot is not None else None
        summary = {"summary": summary_of(result), "evidently": evidently}
        storage.write_bytes(f"{base}.json", json.dumps(summary, default=_json_default).encode())
        result = replace(result, report_uri=f"{base}.html" if snapshot else f"{base}.json")
    log.info("drift columns analysed: %d, decision: %s", len(columns), result.decision)
    return result


def summary_of(result: DriftResult) -> dict:
    return {
        "report_id": result.report_id,
        "window": {"start": iso(result.window.start), "end": iso(result.window.end)},
        "rows": result.rows,
        "signals": asdict(result.signals),
        "decision": asdict(result.decision),
        "recall_at_p90": result.recall_at_p90,
        "labeled_rows": result.labeled_rows,
        "model_version": result.model_version,
    }


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_default(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, datetime):
        return iso(value)
    return str(value)
