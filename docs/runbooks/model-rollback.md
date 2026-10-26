# Model rollback

Use when the champion promoted by the agent (or by hand) performs worse in production: fraud rate jumps on Grafana, analysts report false positives, p95 latency climbs. Rolling back is moving `@champion` back to an earlier version; the versions themselves are never deleted.

## 1. Pick the version

- MLflow UI, model `fraud-xgb`: each version has the tags `run_id` (agent run that produced it), `data_window`, `gate_passed`, `gate_reasons`.
- Dashboard, **Models** page: the promotion history with previous and new version, linked to the agent run.
- Grafana, **Served model version** and **Fraud rate** by `model_version`: when the change started.

The version to go back to is usually `previous_version` of the last `model.promoted`.

## 2. Move the alias

`registry.promote --version N` moves `@champion` to version `N` and copies that version's reference sample to `datasets/reference/reference.parquet`, so drift-monitor compares against the model actually served.

```bash
# Kubernetes: reach MLflow and MinIO from the laptop (port-forward is not affected by the network policies)
kubectl -n infinity port-forward svc/mlflow 5000:5000 &
kubectl -n infinity port-forward svc/minio 9000:9000 &

cd pipelines
MLFLOW_TRACKING_URI=http://localhost:5000 MLFLOW_S3_ENDPOINT_URL=http://localhost:9000 \
S3_ENDPOINT_URL=http://localhost:9000 AWS_ACCESS_KEY_ID=minio AWS_SECRET_ACCESS_KEY=minio12345 \
  uv run python -m registry.promote --version 3
# {"model_name": "fraud-xgb", "version": "3", "alias": "champion", "previous_version": "4"}
```

With Docker Compose the same command works against the published ports (`MLFLOW_HOST_PORT`, `MINIO_HOST_PORT`).

## 3. Tell the services

fastapi-ml reloads on `model.promoted`, and the backend's Models page is built from it. Publish the event with `reason: rollback` and the fields printed above (skip this step if `registry.promote` already published it):

```bash
event=$(jq -nc --arg id "$(uuidgen | tr A-Z a-z)" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{event_id: $id, timestamp: $ts, run_id: null, model_name: "fraud-xgb", version: "3",
    alias: "champion", previous_version: "4", reason: "rollback"}')
echo "fraud-xgb|$event" | kubectl -n infinity exec -i kafka-0 -- /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 --topic model.promoted --property parse.key=true --property key.separator='|'
```

Compose: `docker compose -f infra/docker-compose.yml exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 ...` with the same arguments. The schema is `libs/contracts/events/model.promoted.v1.json`.

Without Kafka, reload each replica by hand: `POST /model/reload` on every fastapi-ml pod (`kubectl -n infinity port-forward pod/<pod> 8000:8000`).

## 4. Check

```bash
kubectl -n infinity port-forward svc/fastapi-ml 8000:8000 &
curl -s localhost:8000/model | jq '{version, last_reload_error}'
```

Grafana **Served model version** shows one version for all replicas and **Model reloads** a `success` bar. If `last_reload_error` is set, the replica kept the previous model: check MLflow and MinIO reachability and retry `POST /model/reload`.

## 5. Afterwards

The bad version stays registered and keeps its tags, so the comparison can be replayed. Write down why it was rolled back in the incident notes (a promoted run can no longer be rejected), and reread the drift report that triggered the promotion: a data incident read as drift, or a PR-AUC measured on too few labels, are the usual causes. The next drift alert compares challengers with the restored champion.
