from prometheus_client import Counter, Gauge

RUNS_STARTED = Counter("agent_runs_started_total", "Graph runs started from a drift alert")
RUNS_FINISHED = Counter("agent_runs_finished_total", "Graph runs that reached an end", ["outcome"])
ALERTS_ATTACHED = Counter(
    "agent_alerts_attached_total", "Drift alerts attached to the run already in progress"
)
EVENTS_PUBLISHED = Counter("agent_events_published_total", "agent.events messages", ["step"])
ACTIVE_RUN = Gauge("agent_active_run", "1 while a run is in progress or waiting for approval")
