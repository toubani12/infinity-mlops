# fastapi-ml

Scores transactions with the `fraud-xgb` model behind the `@champion` alias in MLflow.
It implements `libs/contracts/openapi/inference.v1.yaml`.

| Method | Path | Behaviour |
|---|---|---|
| POST | `/predict` | score one transaction; 422 when a V feature is missing or unknown, 503 without a model |
| GET | `/model` | name, version, alias, load time and threshold of the served model |
| POST | `/model/reload` | load the version behind the alias and swap it in; 503 keeps the previous model |
| GET | `/health` | `ok` with a model, `degraded` without |
| GET | `/metrics` | Prometheus: `http_request_duration_seconds`, `predictions_total`, `fraud_score`, `model_reloads_total`, `kafka_messages_total`, `kafka_batch_size` |

The model is loaded at startup (FastAPI lifespan). If the registry is unreachable the service
still starts, answers 503 and retries every `MODEL_RETRY_SECONDS` until a load succeeds. A reload loads the new version next to the
current one and swaps the reference only on success, so `/predict` keeps serving during and after
a failed reload. `is_fraud` is `fraud_score >= FRAUD_THRESHOLD`.

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

## Configuration

| Variable | Default |
|---|---|
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` |
| `MODEL_NAME` | `fraud-xgb` |
| `MODEL_ALIAS` | `champion` |
| `FRAUD_THRESHOLD` | `0.5` |
| `MODEL_RETRY_SECONDS` | `15` |
| `KAFKA_ENABLED` | `false` |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| `KAFKA_INPUT_TOPIC` / `KAFKA_OUTPUT_TOPIC` | `transaction.raw` / `transaction.scored` |
| `KAFKA_GROUP_ID` | `fastapi-ml` |
| `KAFKA_BATCH_SIZE` / `KAFKA_MAX_WAIT_MS` | `64` / `50` |
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
