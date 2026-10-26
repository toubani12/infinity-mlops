# Contracts

Source of truth between services. Every producer and consumer codes against these files.

| Topic | Producer | Consumers | Key | Retention |
|---|---|---|---|---|
| `transaction.raw` | backend-spring | fastapi-ml | `transaction_id` | 7 days |
| `transaction.scored` | fastapi-ml | backend-spring, drift-monitor (via MinIO logs) | `transaction_id` | 7 days |
| `drift.detected` | drift-monitor | agents-langgraph | `report_id` | 30 days |
| `agent.events` | agents-langgraph | backend-spring | `run_id` | 30 days |
| `agent.commands` | backend-spring | agents-langgraph | `run_id` | 30 days |
| `model.promoted` | agents-langgraph | fastapi-ml, backend-spring | `model_name` | 30 days |

Feature names are lowercase (`v1` to `v28`, `amount`) on the wire, whatever the casing of the source dataset.

## Versioning

Each schema carries its major version in the file name. A breaking change adds `<topic>.v2.json` next to v1; both stay until every consumer has migrated. Additive optional fields are not breaking.

## Checks

```bash
uv sync && uv run pytest -q
```

The tests validate each schema against JSON Schema 2020-12 and each file in `examples/` against its schema.
