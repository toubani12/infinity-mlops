# Model rollback

Use when the champion promoted by the agent (or by hand) performs worse in production: fraud rate jumps on Grafana, analysts report false positives, p95 latency climbs. Rolling back is moving `@champion` back to an earlier version; the versions themselves are never deleted.

## 1. Pick the version

- MLflow UI, model `fraud-xgb`: each version has the tags `run_id` (agent run that produced it), `data_window`, `gate_passed`, `gate_reasons`, and `previous_champion` when `registry.promote` moved the alias.
- Dashboard, **Models** page: the promotion history with previous and new version, linked to the agent run.
- Grafana, **Served model version** and **Fraud rate** by `model_version`: when the change started.

The version to go back to is usually `previous_version` of the last `model.promoted`. The agent moves `@champion` with a plain alias call and writes no `previous_champion` tag, so after an agent promotion always pass that version with `--to`.

## 2. Move the alias and publish model.promoted

`registry.promote rollback --to N` moves `@champion` to version `N`, copies its reference sample to `datasets/reference/reference.parquet` and prints the `model.promoted` payload with `reason: rollback`. With `--kafka-bootstrap` it also publishes it, keyed by `model_name`: every fastapi-ml replica reloads and the backend's Models page records the rollback. drift-monitor follows the `reference_uri` tag of the new champion on its next run.

Docker Compose, from the host:

```bash
cd pipelines
MLFLOW_TRACKING_URI=http://localhost:5000 MLFLOW_S3_ENDPOINT_URL=http://localhost:9000 \
S3_ENDPOINT_URL=http://localhost:9000 AWS_ACCESS_KEY_ID=minio AWS_SECRET_ACCESS_KEY=minio12345 \
  uv run python -m registry.promote rollback --to 3 --kafka-bootstrap localhost:9092
```

Kubernetes: reach MLflow and MinIO through port-forwards (not affected by the network policies). Kafka advertises `kafka:9092`, which the laptop cannot resolve, so publish the printed event through the broker pod:

```bash
kubectl -n infinity port-forward svc/mlflow 5000:5000 &
kubectl -n infinity port-forward svc/minio 9000:9000 &
cd pipelines
event=$(MLFLOW_TRACKING_URI=http://localhost:5000 MLFLOW_S3_ENDPOINT_URL=http://localhost:9000 \
  S3_ENDPOINT_URL=http://localhost:9000 AWS_ACCESS_KEY_ID=minio AWS_SECRET_ACCESS_KEY=minio12345 \
  uv run python -m registry.promote rollback --to 3)
echo "fraud-xgb|$event" | kubectl -n infinity exec -i kafka-0 -- /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 --topic model.promoted --property parse.key=true --property key.separator='|'
```

Without Kafka, reload each replica by hand: `POST /model/reload` on every fastapi-ml pod (`kubectl -n infinity port-forward pod/<pod> 8000:8000`).

## 3. Check the alias

```bash
curl -s "localhost:5000/api/2.0/mlflow/registered-models/alias?name=fraud-xgb&alias=champion" | jq .model_version.version
```

## 4. Check the served model

```bash
kubectl -n infinity port-forward svc/fastapi-ml 8000:8000 &
curl -s localhost:8000/model | jq '{version, last_reload_error}'
```

Grafana **Served model version** shows one version for all replicas and **Model reloads** a `success` bar. If `last_reload_error` is set, the replica kept the previous model: check MLflow and MinIO reachability and retry `POST /model/reload`.

## 5. Afterwards

The bad version stays registered and keeps its tags, so the comparison can be replayed. Write down why it was rolled back in the incident notes (a promoted run can no longer be rejected), and reread the drift report that triggered the promotion: a data incident read as drift, or a PR-AUC measured on too few labels, are the usual causes. The next drift alert compares challengers with the restored champion.
