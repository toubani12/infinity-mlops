# fastapi-ml

Scores transactions with the `fraud-xgb` model behind the `@champion` alias in MLflow.
It implements `libs/contracts/openapi/inference.v1.yaml`.

| Method | Path | Behaviour |
|---|---|---|
| POST | `/predict` | score one transaction; 422 when a V feature is missing or unknown, 503 without a model |
| GET | `/model` | name, version, alias, load time and threshold of the served model, `last_reload_error` when the last reload failed |
| POST | `/model/reload` | load the version behind the alias and swap it in; 503 keeps the previous model |
| GET | `/health` | `ok` with a model, `degraded` without |
| GET | `/metrics` | Prometheus: `http_request_duration_seconds`, `predictions_total`, `fraud_score`, `model_reloads_total`, `served_model_info{model_name,version}`, `model_events_total`, `kafka_messages_total`, `kafka_batch_size`, `prediction_log_rows_total` |

The model is loaded at startup (FastAPI lifespan). If the registry is unreachable the service
still starts, answers 503 and retries every `MODEL_RETRY_SECONDS` until a load succeeds. A reload loads the new version next to the
current one and swaps the reference only on success, so `/predict` keeps serving during and after
a failed reload. `is_fraud` is `fraud_score >= FRAUD_THRESHOLD`.

## Hot reload on `model.promoted`

Every replica subscribes to `model.promoted` (`MODEL_EVENTS_ENABLED`, on by default) and reloads
`@champion` when an event names its `MODEL_NAME` and alias with a version other than the one it
serves; a promotion and a rollback (`reason: rollback`) are handled the same way. The reload
resolves the alias at load time, so a stale event still ends on what the alias points to.

The consumer group is `fastapi-ml-reload-<hostname>`, one per pod. Kafka gives each message of a
group to a single member, so with the `fastapi-ml` group, or any group shared by the replicas,
only one replica would reload and the others would keep the old model. A group per pod gives
every replica every event, and the pod name keeps the group stable across container restarts,
so a restarted container resumes at its committed offset. A new pod starts at the latest offset
(`auto_offset_reset=latest`): it loads `@champion` at startup and only needs later events.
Groups of deleted pods are cleaned up by the broker once their offsets expire
(`offsets.retention.minutes`, 7 days by default).

A reload loads the new model next to the current one and swaps the reference in one assignment;
`score` reads that reference once per call, so requests in flight finish on the model they
started with and no request fails during a swap (`tests/test_hot_reload.py` hammers `/predict`
with 16 concurrent clients through successful and failed reloads). A failed reload is retried
`MODEL_RELOAD_ATTEMPTS` times, `MODEL_RETRY_SECONDS` apart; after that the previous model keeps
serving, the error is logged and shown in `/model` as `last_reload_error`, and the next event or
`POST /model/reload` tries again. The served version is the `version` field of `/model`, the
`model_version` label of `predictions_total` and the `served_model_info` gauge. Kafka being down
does not block startup: the subscription reconnects every `MODEL_RETRY_SECONDS`.

## Kafka scoring

With `KAFKA_ENABLED=true` the lifespan starts an aiokafka consumer on `transaction.raw`
(group `fastapi-ml`). Messages are collected until `KAFKA_BATCH_SIZE` records or
`KAFKA_MAX_WAIT_MS` have passed, scored in one `predict_proba` call and published to
`transaction.scored` keyed by `transaction_id` (`timestamp` is the scoring time, `latency_ms` the
per-message share of the batch scoring time). Offsets are committed after the broker acknowledged
every scored message of the batch: delivery is at least once, and a failed batch is rewound and
retried. Messages that are not valid JSON or break the v1 schema are logged, counted in
`kafka_messages_total{result="invalid"}` and skipped. No message is consumed while no model is
loaded. Shutdown finishes the current batch, commits, then stops the clients.

## Prediction log

Every score, from `/predict` or Kafka, is buffered and written as parquet to
`predictions/dt=YYYY-MM-DD/hour=HH/part-<uuid>.parquet` when the buffer holds
`PREDICTION_LOG_MAX_ROWS` rows or its oldest row is `PREDICTION_LOG_MAX_SECONDS` old, and once
more at shutdown. Partitions follow the scoring time, so replayed transactions land in the window
drift-monitor reads. Columns: `transaction_id`, `timestamp` (transaction time, UTC), `v1`..`v28`,
`amount`, `fraud_score`, `is_fraud`, `model_version`, `latency_ms`, `label` (nullable, filled only
when `transaction.raw` carries one). A failed write keeps the rows for the next flush; the buffer
is capped at 50 000 rows (`prediction_log_rows_total{result="dropped"}` counts the overflow).
The writer sits behind a `PredictionStore` interface with an S3 (boto3, MinIO) and a local
filesystem implementation.

## Configuration

| Variable | Default |
|---|---|
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` |
| `MODEL_NAME` | `fraud-xgb` |
| `MODEL_ALIAS` | `champion` |
| `FRAUD_THRESHOLD` | `0.5`; `auto` uses the `decision_threshold` tag of the served version (highest recall at 90 % precision on validation), 0.5 if the tag is missing |
| `MODEL_RETRY_SECONDS` | `15` |
| `PREDICTION_LOG_ENABLED` | `true` |
| `PREDICTION_LOG_URI` | `s3://predictions` (a local directory works too) |
| `PREDICTION_LOG_MAX_ROWS` / `PREDICTION_LOG_MAX_SECONDS` | `1000` / `60` |
| `S3_ENDPOINT_URL` | unset; `http://minio:9000` in compose, with `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` |
| `KAFKA_ENABLED` | `false` |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| `KAFKA_INPUT_TOPIC` / `KAFKA_OUTPUT_TOPIC` | `transaction.raw` / `transaction.scored` |
| `KAFKA_GROUP_ID` | `fastapi-ml` |
| `KAFKA_BATCH_SIZE` / `KAFKA_MAX_WAIT_MS` | `64` / `50` |
| `MODEL_EVENTS_ENABLED` | `true` |
| `MODEL_EVENTS_TOPIC` / `MODEL_EVENTS_GROUP_PREFIX` | `model.promoted` / `fastapi-ml-reload` |
| `MODEL_RELOAD_ATTEMPTS` | `3` |
| `MLFLOW_HTTP_REQUEST_MAX_RETRIES` / `MLFLOW_HTTP_REQUEST_TIMEOUT` | `2` / `10` in the image, so a down registry does not block startup for minutes |

Model artifacts are downloaded through the MLflow server (`--serve-artifacts`); set
`MLFLOW_S3_ENDPOINT_URL` and the AWS variables only if the server hands out direct S3 URIs.

## Run

```bash
uv sync
MLFLOW_TRACKING_URI=http://localhost:5000 uv run uvicorn app.main:create_app --factory --port 8000
```

## Test

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Tests inject a model trained in a fixture through the `ModelLoader` interface; the MLflow loader
is tested against a `sqlite:///` registry in a temporary directory.
