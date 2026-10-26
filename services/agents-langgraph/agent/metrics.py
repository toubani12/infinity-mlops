from prometheus_client import Counter, Gauge

RUNS_STARTED = Counter("agent_runs_started_total", "Graph runs started from a drift alert")
RUNS_FINISHED = Counter("agent_runs_finished_total", "Graph runs that reached an end", ["outcome"])
ALERTS_ATTACHED = Counter(
    "agent_alerts_attached_total", "Drift alerts attached to the run already in progress"
)
EVENTS_PUBLISHED = Counter("agent_events_published_total", "agent.events messages", ["step"])
ACTIVE_RUN = Gauge("agent_active_run", "1 while a run is in progress or waiting for approval")
# drift-monitor is a one-shot CronJob with nothing to scrape, and it only publishes when a
# threshold is crossed: these gauges show the last alert, not every monitored window.
DRIFT_SHARE = Gauge("agent_drift_share", "drift_share of the last drift.detected consumed")
DRIFT_ALERT_TIME = Gauge(
    "agent_drift_alert_timestamp_seconds", "Unix time the last drift.detected was consumed"
)
DRIFT_ALERTS = Counter("agent_drift_alerts_total", "Valid drift.detected messages consumed")
