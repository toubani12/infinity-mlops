# agents-langgraph

LangGraph agent of the self-healing loop. It consumes `drift.detected`, qualifies the alert (noise, real drift, data incident), launches the retrain Job for a real drift, rechecks the evaluation gate and asks a human before promoting. Every step is published on `agent.events` (v1).

## Run

```bash
uv sync
uv run python -m agent.main          # http://localhost:8100/health, /metrics, /runs
```

## Test

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q                     # coverage on agent/
```

Tests use fake tools, a recording publisher and the in-memory checkpointer; events are validated against `libs/contracts/events/agent.events.v1.json`.
