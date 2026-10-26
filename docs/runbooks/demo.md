# Demo scenario

Two runs of the same story. The Compose run shows live scoring, alerts and a drift alert in
about five minutes. The Minikube run adds the part Compose cannot do, the retrain Job, and
closes the loop with an approval in the dashboard. Allow 10 minutes for it once images are built.

## Prerequisites

- Docker, `uv`, and the ULB dataset at `data/creditcard.csv` (Kaggle, or the copy published by
  TensorFlow: `curl -o data/creditcard.csv https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv`).
- `infra/env/.env` copied from `.env.example`, with host ports changed if some are taken.

## Compose: scoring, alerts and drift

```bash
make up                                     # Kafka, PostgreSQL, MinIO, MLflow
cd pipelines && uv run python -m training.train \
  --data ../data/creditcard.csv --config configs/xgb_baseline.yaml --bootstrap-champion && cd ..
make up-apps                                # backend, inference, agent, dashboard, monitoring
```

1. Open the dashboard (`http://localhost:3000`, or `FRONTEND_HOST_PORT`) and sign in as an
   `admin` dev user. The header shows the served model version.
2. Normal traffic, with frauds oversampled so alerts appear quickly:

   ```bash
   uv run scripts/seed-transactions.py --rows 1500 --rate 80 --fraud-share 0.02
   ```

   The Transactions page fills live over SSE; the Alerts page lists every score at or above
   `ALERT_THRESHOLD`.
3. Inject drift and send it through the backend:

   ```bash
   cd pipelines && uv run python -m data.simulate_drift --scenario sudden \
     --data ../data/creditcard.csv --rows 3000 --fraud-rate 0.01 --magnitude 1.5 \
     --out ../data/drift-sudden.parquet && cd ..
   uv run scripts/seed-transactions.py --data data/drift-sudden.parquet --rows 3000 --rate 150
   ```

4. Wait one minute for the prediction log to flush, then run one monitoring cycle:

   ```bash
   docker compose -f infra/docker-compose.yml --env-file infra/env/.env --profile apps \
     run --rm drift-monitor
   ```

   The Drift page shows the new report: drift share, drifted features, PR-AUC against the
   reference. The Agent page shows the run the alert started (`received`, `qualified`
   real_drift, `retrain_started`). Under Compose it stops at `failed`: there is no Kubernetes
   API to create the retrain Job.

## Minikube: the full self-healing loop

```bash
make minikube        # cluster, images, overlay, rollouts
make e2e-demo        # scripted version of the steps below, checks every stage
```

To present it by hand instead of `make e2e-demo`:

1. Port-forward the dashboard and backend as printed by `make minikube`, sign in as `admin`.
2. Seed normal traffic, then drifted traffic, as in the Compose run (`--api` points at the
   forwarded backend).
3. The `drift-monitor` CronJob runs every 5 minutes in the minikube overlay; its alert starts an
   agent run. Follow it on the Agent page: `retrain_started` (a Job named `retrain-<run id>`
   appears in `kubectl -n infinity get jobs`), `retrain_finished`, `evaluated`.
4. When the challenger beats the champion the run stops at `approval_requested`. The run detail
   shows champion and challenger side by side against the gate: PR-AUC, recall at 90 %
   precision, p95 latency under 50 ms.
5. Approve with a short reason. The run moves to `approved`, `promoted`, `completed`; the Models
   page shows the new version, and the header badge changes once fastapi-ml has reloaded it.
6. To show the other branch, inject drift again and reject: the champion stays and the reason
   appears in the timeline.

Rollback, if needed during the demo: [model-rollback.md](model-rollback.md).
