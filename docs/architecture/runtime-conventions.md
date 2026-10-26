# Runtime conventions

Shared by every service so they integrate without guessing. Changing a value here is a change for everyone.

## Ports (host, local stack)

| Service | Port |
|---|---|
| backend-spring | 8080 |
| fastapi-ml | 8000 |
| agents-langgraph (health + metrics) | 8100 |
| drift-monitor (one-shot job, metrics when run as a server) | 8200 |
| frontend-next | 3000 |
| Kafka (host listener) | 9092 (inside compose network: `kafka:29092`) |
| PostgreSQL | 5432 |
| MinIO API / console | 9000 / 9001 |
| MLflow | 5000 |
| Prometheus / Grafana | 9090 / 3001 |

## Environment variables

| Variable | Default (local) | Used by |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | all |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | pipelines, fastapi-ml, agents-langgraph |
| `MLFLOW_S3_ENDPOINT_URL` | `http://localhost:9000` | pipelines, fastapi-ml, agents-langgraph |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | `minio` / `minio12345` | anything reading MinIO |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | drift-monitor, fastapi-ml logging |
| `MODEL_NAME` | `fraud-xgb` | pipelines, fastapi-ml, agents-langgraph |
| `FRAUD_THRESHOLD` | `0.5` | fastapi-ml |
| `ALERT_THRESHOLD` | `0.5` | backend-spring |
| `DATABASE_URL` (Python) | `postgresql://infinity:infinity@localhost:5432/agent` | agents-langgraph checkpointer |
| `SPRING_DATASOURCE_URL` | `jdbc:postgresql://localhost:5432/infinity` | backend-spring |
| `JWT_SECRET` | 32+ byte dev secret in `.env.example` | backend-spring |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8080` | frontend-next |
| `LLM_PROVIDER` | `none` (rules only), `ollama`, `anthropic`, `openai` | agents-langgraph |

PostgreSQL databases: `infinity` (backend), `mlflow` (MLflow backend store), `agent` (LangGraph checkpoints). User and password `infinity` / `infinity` locally.

## Model

- Registered model name: `fraud-xgb`. Aliases: `champion`, `challenger`. No stages.
- Feature order, lowercase on the wire and in training: `v1` … `v28`, `amount`. `Time` from the CSV is only used to order rows for the time split, never as a feature.
- The logged model is an MLflow XGBoost model (`mlflow.xgboost`), so any consumer loads it with `mlflow.pyfunc.load_model("models:/fraud-xgb@champion")` and calls `predict_proba` through the native flavor when needed.
- Metrics logged on every training run: `pr_auc`, `recall_at_p90`, `roc_auc`, `p95_latency_ms`, plus `champion_pr_auc`, `champion_recall_at_p90`, `champion_p95_latency_ms` when a champion exists, and the tag `gate_passed=true|false`.
- Tags on the registered version: `run_id` of the agent run that produced it (when retrained by the agent), `data_window`.

## Data and object storage (MinIO buckets)

| Bucket / prefix | Content | Writer |
|---|---|---|
| `mlflow/` | MLflow artifacts | MLflow |
| `datasets/reference/reference.parquet` | reference sample used by drift-monitor | pipelines training |
| `datasets/raw/creditcard.parquet` | full ingested dataset | pipelines ingest |
| `predictions/dt=YYYY-MM-DD/hour=HH/part-<uuid>.parquet` | prediction log | fastapi-ml |
| `drift-reports/YYYY/MM/DD/HH/<report_id>.html` and `.json` | Evidently reports | drift-monitor |

Prediction log columns: `transaction_id`, `timestamp`, `v1`..`v28`, `amount`, `fraud_score`, `is_fraud`, `model_version`, `latency_ms`, `label` (nullable int).

The real dataset lives in `data/creditcard.csv` at the repo root (git-ignored). `pipelines/data/synthetic.py` produces a frame with the same schema for tests, CI and demos when the real file is absent.

## Kafka

Topics and keys from `libs/contracts/README.md`. Consumer groups: `fastapi-ml`, `backend-spring`, `agents-langgraph`. JSON values, UTF-8, no schema registry; producers validate against the v1 schema in tests.

## Backend REST and SSE (backend-spring)

| Method | Path | Role |
|---|---|---|
| POST | `/api/transactions` | analyst |
| GET | `/api/transactions?page&size&fraudOnly` | analyst |
| GET | `/api/alerts?page&size&status` | analyst |
| PATCH | `/api/alerts/{id}` (status `OPEN`/`ACKNOWLEDGED`/`CLOSED`) | analyst |
| GET | `/api/drift/reports?page&size` | analyst |
| GET | `/api/agent/runs` and `/api/agent/runs/{runId}` | analyst |
| POST | `/api/agent/runs/{runId}/approve` | admin |
| POST | `/api/agent/runs/{runId}/reject` body `{ "reason": "..." }` | admin |
| GET | `/api/models/versions` | analyst |
| GET | `/api/stream/transactions`, `/api/stream/alerts`, `/api/stream/agent` (SSE) | analyst |
| POST | `/api/auth/dev-token` body `{ "username", "role" }` (profile `local` only) | public |

The backend also consumes `drift.detected` and `model.promoted` to serve the Drift and Models pages.

## Python services

uv, Python 3.12, one `pyproject.toml` and `uv.lock` per service, `ruff check`, `ruff format --check`, `pytest -q --cov`. Dockerfiles use `python:3.12-slim` with `uv sync --frozen --no-dev`.

## Images

`ghcr.io/toubani12/infinity-mlops/<service>:<git sha>` and `:latest` on main. Service names: `backend-spring`, `fastapi-ml`, `frontend-next`, `agents-langgraph`, `drift-monitor`, `pipelines`.
