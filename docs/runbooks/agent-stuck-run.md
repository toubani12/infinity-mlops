# Agent: stuck run

The agent runs one retrain at a time. A run that never ends blocks every later drift alert, which is attached to it instead of starting a new run. Start with the state the agent itself reports:

```bash
kubectl -n infinity port-forward svc/agents-langgraph 8100:8100 &
curl -s localhost:8100/health    # active_run_id
curl -s localhost:8100/runs      # runs since the process started, with status and outcome
kubectl -n infinity logs deploy/agents-langgraph --tail 200
```

The dashboard's Agent page (`GET /api/agent/runs/{runId}`) shows the same run from the `agent.events` the backend received, with its timeline. Grafana **Agent run in progress** is 1 while the slot is taken.

## Waiting for approval

Status `AWAITING_APPROVAL`, last step `approval_requested`. This is by design: nothing moves until an admin decides.

- Decide on the run page, or `POST /api/agent/runs/{runId}/approve` / `/reject` with `{"reason": "..."}` and an `admin` token.
- The run shows a `pendingCommand` but stays waiting: the backend sent the command on `agent.commands` and the agent has not answered. Check the agent log for `ignoring approve for unknown run` (the checkpoint is gone, see below) or Kafka consumer errors. Resending is safe: the agent ignores a command for a run that is no longer waiting.
- The agent restarted: on start it scans the PostgreSQL checkpoints and gives the slot back to the run paused on `await_approval`, so the approval still works after a restart.

## Retrain Job failed or hangs

Status `RUNNING`, last step `retrain_started`, or `FAILED` with the Job reason and the end of the trainer log in the message.

```bash
kubectl -n infinity get jobs -l app.kubernetes.io/component=retrain
kubectl -n infinity describe job retrain-<run_id[:8]>
kubectl -n infinity logs job/retrain-<run_id[:8]>
```

| Symptom | Cause | Fix |
|---|---|---|
| pod `Pending` | not enough CPU or memory for the 1 CPU / 1 Gi request | free resources or raise `MINIKUBE_MEMORY` |
| `ErrImagePull` | `pipelines:latest` absent from the node | rebuild it (`make minikube`), the template uses `IfNotPresent` |
| exit 1, MLflow or S3 errors | MLflow or MinIO unreachable, or a network policy misses the Job label | `kubectl -n infinity get networkpolicy`, the Job pods need `app.kubernetes.io/component: retrain` |
| exit 1, data errors | `datasets/raw/creditcard.parquet` missing or invalid | run the ingestion (`python -m data.ingest`) |
| no result | `activeDeadlineSeconds` (30 min) or the agent's `RETRAIN_TIMEOUT_SECONDS` (35 min) reached | the agent publishes `failed` and frees the slot |

A failed run frees the slot; the next `drift.detected` starts a new run. To retry now, let drift-monitor run again (`kubectl -n infinity create job drift-now --from=cronjob/drift-monitor`). Deleting a running retrain Job makes the agent publish `failed` on its next poll.

## Checkpointer problems

Graph state lives in PostgreSQL database `agent` (`DATABASE_URL`), tables `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, one thread per `run_id`.

- `DATABASE_URL is empty, graph state lives in memory` in the log: a restart loses every waiting run. Set `DATABASE_URL` (Kubernetes sets it from `platform-secrets`).
- The agent does not start and the log shows a PostgreSQL error: check the `postgres` pod and that database `agent` exists (`01-create-databases.sql` runs only on an empty volume).
- A run must be abandoned (corrupted state, a decision that will never come): reject it from the dashboard if it is waiting. Otherwise remove its thread and restart the agent so it forgets the slot:

```bash
kubectl -n infinity exec -it postgres-0 -- psql -U infinity -d agent -c \
  "delete from checkpoint_writes where thread_id = '<run_id>';
   delete from checkpoint_blobs where thread_id = '<run_id>';
   delete from checkpoints where thread_id = '<run_id>';"
kubectl -n infinity rollout restart deployment/agents-langgraph
```

The backend still shows the run with its last status; it is history, not state.
