import json
from datetime import timedelta

import numpy as np
import pytest

from monitor.report import (
    Window,
    analyze,
    label_metrics,
    load_window,
    missing_features,
    out_of_range_share,
)
from monitor.storage import Storage
from monitor.thresholds import Thresholds
from tests.conftest import NOW, frame, write_partition

SHIFTED = {f"v{i}": 1.5 for i in (1, 2, 3, 4, 10, 12, 14, 17, 20, 25)}


def test_window_partitions() -> None:
    window = Window.last_hours(NOW, 2)
    assert window.start == NOW.replace(hour=9, minute=0)
    assert window.partitions() == ["dt=2026-10-26/hour=09/", "dt=2026-10-26/hour=10/"]
    assert Window.last_hours(NOW, 1).partitions() == ["dt=2026-10-26/hour=10/"]


def test_load_window_reads_only_partitions_in_window(tmp_path) -> None:
    write_partition(tmp_path, frame(10, seed=1), NOW)
    write_partition(tmp_path, frame(5, seed=2), NOW, name="part-b")
    write_partition(tmp_path, frame(7, seed=3), NOW - timedelta(hours=3))
    assert len(load_window(Storage(), str(tmp_path), Window.last_hours(NOW, 1))) == 15
    assert load_window(Storage(), str(tmp_path / "none"), Window.last_hours(NOW, 1)).empty


def test_missing_features_detects_absent_null_and_stuck_columns() -> None:
    reference, current = frame(200), frame(200, seed=1)
    current = current.drop(columns=["v2"]).assign(v5=np.nan, v7=0.0)
    assert missing_features(current, reference) == ["v2", "v5", "v7"]
    assert missing_features(frame(200, seed=1), reference) == []


def test_partial_outage_counts_as_missing() -> None:
    reference, current = frame(1000), frame(1000, seed=1)
    current.loc[:299, "v4"] = np.nan
    current.loc[:299, "v10"] = 0.0
    current.loc[:49, "v12"] = np.nan
    assert missing_features(current, reference) == ["v4", "v10"]
    assert missing_features(current, reference, max_share=0.5) == []


def test_out_of_range_share() -> None:
    reference, current = frame(1000), frame(1000, seed=1)
    assert out_of_range_share(current, reference, 0.1) < 0.01
    current.loc[:99, "v14"] = 80.0
    current.loc[100:149, "amount"] = -5.0
    assert out_of_range_share(current, reference, 0.1) == pytest.approx(0.15, abs=0.01)


def test_label_metrics() -> None:
    thresholds = Thresholds()
    pr_auc, recall, labeled = label_metrics(frame(2000), thresholds)
    assert pr_auc == 1.0 and recall == 1.0 and labeled == 2000
    assert label_metrics(frame(50), thresholds)[0] is None
    unlabeled = frame(2000).assign(label=None)
    assert label_metrics(unlabeled, thresholds) == (None, None, 0)
    assert label_metrics(frame(10).drop(columns=["label"]), thresholds) == (None, None, 0)


def test_stable_window_is_not_published() -> None:
    result = analyze(frame(2000, seed=1), frame(2000), Window.last_hours(NOW, 1), Thresholds())
    assert result.signals.drift_share <= 0.3
    assert not result.decision.publish
    assert result.model_version == "3"


def test_shifted_window_is_published_and_saved(tmp_path) -> None:
    result = analyze(
        frame(2000, seed=1, shift=SHIFTED),
        frame(2000),
        Window.last_hours(NOW, 1),
        Thresholds(),
        storage=Storage(),
        reports_uri=str(tmp_path),
    )
    assert set(SHIFTED) <= set(result.signals.drifted_features)
    assert result.signals.drift_share > 0.3 and result.decision.publish
    html = tmp_path / "2026" / "10" / "26" / "10" / f"{result.report_id}.html"
    assert result.report_uri == str(html) and html.stat().st_size > 1000
    saved = json.loads(html.with_suffix(".json").read_text())
    assert saved["summary"]["decision"]["publish"] is True
    assert saved["evidently"]["metrics"]


def test_pr_auc_drop_alone_triggers() -> None:
    current = frame(2000, seed=1, informative=False)
    result = analyze(current, frame(2000), Window.last_hours(NOW, 1), Thresholds())
    assert result.signals.reference_pr_auc == 1.0
    assert result.signals.pr_auc < 0.5
    assert result.decision.publish
    assert result.decision.reasons[0].startswith("pr-auc dropped")


def test_data_incident_with_every_feature_missing(tmp_path) -> None:
    current = frame(300).drop(columns=[f"v{i}" for i in range(1, 29)] + ["amount"])
    result = analyze(
        current,
        frame(300),
        Window.last_hours(NOW, 1),
        Thresholds(),
        storage=Storage(),
        reports_uri=str(tmp_path),
    )
    assert result.signals.drift_share == 1.0
    assert result.report_uri.endswith(".json")
