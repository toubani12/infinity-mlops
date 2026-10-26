import json

import pytest

import monitor.__main__ as entry
from monitor.storage import Storage
from monitor.thresholds import Thresholds
from tests.conftest import NOW, FakePublisher, frame, write_partition


@pytest.fixture
def layout(tmp_path):
    reference = tmp_path / "datasets" / "reference" / "reference.parquet"
    reference.parent.mkdir(parents=True)
    frame(2000).to_parquet(reference, index=False)
    settings = entry.Settings(
        reference_uri=str(reference),
        predictions_uri=str(tmp_path / "predictions"),
        reports_uri=str(tmp_path / "drift-reports"),
    )
    return tmp_path, settings


def test_drifted_window_publishes_once(layout) -> None:
    root, settings = layout
    write_partition(
        root / "predictions",
        frame(
            1500,
            seed=4,
            shift={
                "v4": 2,
                "v10": 2,
                "v12": 2,
                "v14": 2,
                "v17": 2,
                "v3": 2,
                "v11": 2,
                "v16": 2,
                "v7": 2,
            },
        ),
        NOW,
    )
    publisher = FakePublisher()
    result = entry.run(settings, Thresholds(), Storage(), publisher, now=NOW)
    assert result is not None and len(publisher.events) == 1
    assert publisher.events[0]["report_id"] == result.report_id
    assert list((root / "drift-reports").rglob("*.html"))


def test_small_window_is_skipped(layout) -> None:
    root, settings = layout
    write_partition(root / "predictions", frame(50, seed=4), NOW)
    publisher = FakePublisher()
    assert entry.run(settings, Thresholds(), Storage(), publisher, now=NOW) is None
    assert publisher.events == []


def test_main_reads_environment(layout, monkeypatch, capsys) -> None:
    root, settings = layout
    write_partition(root / "predictions", frame(500, seed=4), entry.datetime.now(entry.UTC))
    monkeypatch.setenv("REFERENCE_URI", settings.reference_uri)
    monkeypatch.setenv("PREDICTIONS_URI", settings.predictions_uri)
    monkeypatch.setenv("REPORTS_URI", settings.reports_uri)
    monkeypatch.setattr(entry, "KafkaPublisher", lambda servers: FakePublisher())
    assert entry.main() == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["rows"] == 500
