# agents-langgraph

LangGraph agent of the self-healing loop. It consumes `drift.detected`, qualifies the alert (noise, real drift, data incident), launches the retrain Job for a real drift, rechecks the evaluation gate, and waits for a human decision on `agent.commands` before moving `@champion`. Every step is published on `agent.events` (v1), keyed by `run_id`.

Pinned: `langgraph==1.2.17`, `langgraph-checkpoint-postgres==3.2.0`, `mlflow-skinny==3.17.2`.

## Graph

```mermaid
flowchart TD
    START((start)) --> receive --> qualify
    qualify -- data_incident --> escalate --> END((end))
    qualify -- noise --> end_noise --> END
    qualify -- real_drift --> retrain
    retrain -- job failed --> fail --> END
    retrain -- job succeeded --> evaluate
    evaluate -- gate failed --> keep_champion --> END
    evaluate -- gate passed --> request_approval --> await_approval
    await_approval -. "interrupt, resumed by agent.commands" .-> await_approval
    await_approval -- approve --> promote --> END
    await_approval -- reject --> reject --> END
```

`request_approval` publishes the request and `await_approval` holds the `interrupt(...)`: LangGraph re-runs an interrupted node from its start on resume, so the publication sits in the node before it and is never repeated.

Events published per path (`agent.events` step, then `decision` where set):

| Path | Steps |
|---|---|
| noise | `received`, `qualified` (noise), `completed` (noise) |
| data incident | `received`, `qualified` (data_incident), `escalated` (data_incident), `completed` (data_incident) |
| retrain job failed | `received`, `qualified` (real_drift), `retrain_started`, `failed` |
| gate failed | `received`, `qualified`, `retrain_started`, `retrain_finished`, `evaluated` (keep_champion), `completed` (keep_champion) |
| approved | ... `evaluated` (promote), `approval_requested` (promote, `requires_approval: true`), `approved` (promote), `promoted` (promote), `completed` (promote), plus `model.promoted` with `reason: promotion` |
| rejected | ... `approval_requested`, `rejected` (keep_champion, reason in payload), `completed` (keep_champion) |
| tool error | the steps reached so far, then `failed` with the exception in `message` |
| alert during a run | `received` on the active run with `payload.attached: true` |

## Guardrails

- Decisions are rules. Qualification: data incident if `missing_features` is not empty or `out_of_range_share` > `OUT_OF_RANGE_THRESHOLD`; noise if `drift_share` <= `DRIFT_SHARE_THRESHOLD` and the PR-AUC drop <= `PR_AUC_DROP_THRESHOLD`; real drift otherwise. The gate is rechecked by the agent: training tag `gate_passed=true`, challenger PR-AUC and recall at 90 % precision above the champion, p95 latency under `MAX_P95_LATENCY_MS`. When `LLM_PROVIDER` is not `none`, the LLM only adds an explanation to the `qualified` event.
- One retrain at a time. A run holds the slot from `received` until it ends, including while it waits for approval. Another alert in that window is attached to the active run. Run ids derive from the report id, so a redelivered alert does not start a second run.
- Closed tool set, each behind an interface (`agent/tools/`). No shell and no generic Kubernetes access.

| Tool | Implementation | Reaches |
|---|---|---|
| `read_report` | `PayloadReportReader` | the `drift.detected` message |
| `launch_retrain_job` | `KubernetesRetrainLauncher` | creates `retrain-<run_id[:8]>` in namespace `infinity`, polls it until success, failure or `RETRAIN_TIMEOUT_SECONDS` |
| `read_mlflow_metrics` | `MlflowMetricsReader` | the `fraud-xgb` version tagged `run_id=<run_id>`, its run metrics and the `@champion` version |
| `request_approval` | `EventApprovalRequester` | publishes `approval_requested` on `agent.events` |
| `move_alias` | `MlflowAliasMover` | moves `@champion` only |

The retrain Job follows [docs/architecture/retrain-contract.md](../../docs/architecture/retrain-contract.md): the launcher loads the template from `RETRAIN_TEMPLATE_PATH`, sets the name, adds the label `infinity.io/run-id`, overrides `RUN_ID`, `WINDOW_DAYS`, `TRAIN_CONFIG`, `DATA_URI` and `PREDICTIONS_URI` on container `trainer`, and leaves everything else as written. A 409 on create means the Job of that run already exists, so the launcher follows it. On failure the message carries the Job reason and the last lines of the trainer log.

In Kubernetes the ServiceAccount `agents-langgraph` is bound to a Role that allows `create, get, list, watch` on `jobs` and `get, list` on `pods` and `pods/log`, in namespace `infinity` only. The template is mounted from the ConfigMap `retrain-job-template` at `/etc/agent/retrain/retrain-job.yaml`; the volume is optional so the pod starts before the template exists.

Follow-up once `k8s/jobs/retrain-job.yaml` is on main: add `k8s/jobs/kustomization.yaml` with a `configMapGenerator` named `retrain-job-template` (`files: [retrain-job.yaml]`) and list `../../jobs` in `k8s/base/agents-langgraph/kustomization.yaml`. Kustomize then rewrites the hashed name in the Deployment, and the pod rolls when the template changes.

## Approval and restarts

Graph state is checkpointed per run (`thread_id = run_id`) in PostgreSQL through `AsyncPostgresSaver` when `DATABASE_URL` is set (tables created on start), in memory otherwise. On start the agent scans the checkpoints for a run paused on `await_approval` and gives it the retrain slot back. A command on `agent.commands` resumes that thread with `Command(resume=...)`; a command for an unknown run, a run that is not waiting, or an invalid command (reject without a reason) is logged and ignored.

## Configuration

| Variable | Default |
|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| `CONSUMER_GROUP` | `agents-langgraph` |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` |
| `MODEL_NAME` | `fraud-xgb` |
| `DATABASE_URL` | empty: in-memory checkpoints |
| `LLM_PROVIDER` | `none` (`ollama`, `anthropic`, `openai`) |
| `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT_SECONDS` | provider defaults, `20` |
| `DRIFT_SHARE_THRESHOLD`, `PR_AUC_DROP_THRESHOLD`, `OUT_OF_RANGE_THRESHOLD` | `0.3`, `0.05`, `0.05` |
| `MAX_P95_LATENCY_MS` | `50` |
| `K8S_NAMESPACE` | `infinity` |
| `RETRAIN_TEMPLATE_PATH` | `/etc/agent/retrain/retrain-job.yaml` |
| `RETRAIN_POLL_SECONDS`, `RETRAIN_TIMEOUT_SECONDS` | `10`, `2100` |
| `RETRAIN_WINDOW_DAYS`, `RETRAIN_TRAIN_CONFIG`, `RETRAIN_DATA_URI`, `RETRAIN_PREDICTIONS_URI` | contract defaults |
| `HTTP_PORT` | `8100` |

## Run

```bash
uv sync
uv run python -m agent.main          # http://localhost:8100/health, /metrics, /runs
```

Trigger a run on the local stack (`make up-apps`) by publishing the contract example:

```bash
jq -c . libs/contracts/examples/drift.detected.v1.json | docker compose -f infra/docker-compose.yml \
  exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic drift.detected
curl -s localhost:8100/runs
```

Compose has no Kubernetes API, so a real drift ends with `failed` at `launch_retrain_job` there; set `"drift_share": 0.1` and equal PR-AUCs for the noise path, or a non-empty `missing_features` for the data incident path. The full retrain and approval path runs in minikube. Approve a waiting run through the backend (`POST /api/agent/runs/{runId}/approve`) or by publishing an `agent.commands` message with that `run_id`.

## Test

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q                     # coverage on agent/
AGENT_TEST_DATABASE_URL=postgresql://infinity:infinity@localhost:5432/agent_test uv run pytest -q -m postgres
```

Tests use fake tools, a recording publisher and the in-memory checkpointer; events are validated against the schemas in `libs/contracts/events/`. The `postgres` test is skipped unless `AGENT_TEST_DATABASE_URL` points at a database it may truncate.
