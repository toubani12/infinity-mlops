import json
import logging
import sys
from datetime import UTC, datetime

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from monitor.publisher import KafkaPublisher, Publisher, build_event
from monitor.report import DriftResult, Window, analyze, load_window, summary_of
from monitor.storage import Storage
from monitor.thresholds import Thresholds

log = logging.getLogger("monitor")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    kafka_bootstrap_servers: str = "localhost:9092"
    s3_endpoint_url: str | None = None
    reference_uri: str = "s3://datasets/reference/reference.parquet"
    predictions_uri: str = "s3://predictions"
    reports_uri: str = "s3://drift-reports"
    window_hours: int = Field(default=1, ge=1)
    min_window_rows: int = Field(default=200, ge=1)
    max_report_rows: int = Field(default=50_000, ge=100)


def run(
    settings: Settings,
    thresholds: Thresholds,
    storage: Storage,
    publisher: Publisher,
    now: datetime | None = None,
) -> DriftResult | None:
    window = Window.last_hours(now or datetime.now(UTC), settings.window_hours)
    current = load_window(storage, settings.predictions_uri, window)
    if len(current) < settings.min_window_rows:
        log.info("window has %d rows, below %d: no report", len(current), settings.min_window_rows)
        return None
    reference = storage.read_parquet(settings.reference_uri)
    result = analyze(
        current,
        reference,
        window,
        thresholds,
        storage=storage,
        reports_uri=settings.reports_uri,
        max_rows=settings.max_report_rows,
    )
    if result.decision.publish:
        publisher.publish(build_event(result))
        log.warning("drift.detected published: %s", "; ".join(result.decision.reasons))
    print(json.dumps(summary_of(result), default=str))
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings()
    run(
        settings,
        Thresholds(),
        Storage(endpoint_url=settings.s3_endpoint_url),
        KafkaPublisher(settings.kafka_bootstrap_servers),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
