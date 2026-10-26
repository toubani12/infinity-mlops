# agents-langgraph

LangGraph agent of the self-healing loop. It consumes `drift.detected`, qualifies the alert (noise, real drift, data incident), launches the retrain Job for a real drift, rechecks the evaluation gate and asks a human before promoting. Every step is published on `agent.events` (v1).

## Tools

The graph reaches the outside world only through five tools (`agent/tools/`), each behind an interface so tests swap in fakes. There is no shell and no generic Kubernetes access.

| Tool | Implementation | Reaches |
|---|---|---|
| `read_report` | `PayloadReportReader` | the `drift.detected` message |
| `launch_retrain_job` | `KubernetesRetrainLauncher` | creates `retrain-<run_id[:8]>` in namespace `infinity`, polls it until success, failure or `RETRAIN_TIMEOUT_SECONDS` |
| `read_mlflow_metrics` | `MlflowMetricsReader` | the `fraud-xgb` version tagged `run_id=<run_id>`, its run metrics and the `@champion` version |
| `request_approval` | `EventApprovalRequester` | publishes `approval_requested` on `agent.events` |
| `move_alias` | `MlflowAliasMover` | moves `@champion` only |

The retrain Job follows [docs/architecture/retrain-contract.md](../../docs/architecture/retrain-contract.md): the launcher loads the template from `RETRAIN_TEMPLATE_PATH`, sets the name, adds the label `infinity.io/run-id`, overrides `RUN_ID`, `WINDOW_DAYS`, `TRAIN_CONFIG`, `DATA_URI` and `PREDICTIONS_URI` on container `trainer`, and leaves everything else as written. A 409 on create means the Job of that run already exists, so the launcher follows it instead of failing. On failure the message carries the Job reason and the last lines of the trainer log.

In Kubernetes the ServiceAccount `agents-langgraph` is bound to a Role that allows `create, get, list, watch` on `jobs` and `get, list` on `pods` and `pods/log`, in namespace `infinity` only. The template is mounted from the ConfigMap `retrain-job-template` at `/etc/agent/retrain/retrain-job.yaml`; the volume is optional so the pod starts before the template exists.

Follow-up once `k8s/jobs/retrain-job.yaml` is on main: add `k8s/jobs/kustomization.yaml` with a `configMapGenerator` named `retrain-job-template` (`files: [retrain-job.yaml]`) and list `../../jobs` in `k8s/base/agents-langgraph/kustomization.yaml`. Kustomize then rewrites the hashed name in the Deployment, and the pod rolls when the template changes. Tests use the contract-shaped copy in `tests/fixtures/retrain-job.yaml`.

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
