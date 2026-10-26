# Local stack

Docker Compose stack defined in `infra/docker-compose.yml`. Needs Docker Desktop (or Docker Engine with Compose v2) and about 4 GB of free memory for the infrastructure, 8 GB with the applications.

## Start

```bash
cp infra/env/.env.example infra/env/.env   # optional, the Makefile falls back to .env.example
make up        # Kafka, PostgreSQL, MinIO, MLflow; waits for health, then creates topics
make up-apps   # also builds and starts backend-spring, fastapi-ml, frontend-next, agents-langgraph, drift-monitor
```

`make up` returns when every infrastructure container is healthy. The first run pulls images and builds the MLflow image; later runs take well under a minute.

One-shot containers run on start and exit with code 0:

| Container | Does |
|---|---|
| `minio-init` | Creates buckets `mlflow`, `datasets`, `predictions`, `drift-reports` |
| `kafka-init` | Creates the six topics (`transaction.*` 6 partitions and 7 days retention, `agent.*` 3 partitions, `drift.detected` and `model.promoted` 1 partition, 30 days) |
| PostgreSQL init script | Creates databases `mlflow` and `agent` next to `infinity` on the first start of an empty volume |

`drift-monitor` is also one-shot under Compose: `make up-apps` runs one cycle. Run another with `docker compose -f infra/docker-compose.yml --profile apps run --rm drift-monitor`.

## Endpoints

| Service | From the host | From a container |
|---|---|---|
| Kafka | `localhost:9092` | `kafka:29092` |
| PostgreSQL | `localhost:5432` (`infinity` / `infinity`) | `postgres:5432` |
| MinIO API / console | http://localhost:9000 / http://localhost:9001 (`minio` / `minio12345`) | `http://minio:9000` |
| MLflow | http://localhost:5000 | `http://mlflow:5000` |
| backend-spring | http://localhost:8080 | `http://backend-spring:8080` |
| fastapi-ml | http://localhost:8000 | `http://fastapi-ml:8000` |
| agents-langgraph | http://localhost:8100 | `http://agents-langgraph:8100` |
| frontend-next | http://localhost:3000 | |

## Check health

```bash
make ps                                   # STATUS shows (healthy) for kafka, postgres, minio, mlflow
make topics                               # partitions and retention of every topic
curl -s localhost:5000/health             # MLflow, prints OK
docker compose -f infra/docker-compose.yml exec postgres psql -U infinity -l
make logs s=mlflow
```

MLflow rejects requests whose `Host` header is not in `MLFLOW_SERVER_ALLOWED_HOSTS` (403). Add the hostname there if you reach it through another name.

## Stop and reset

```bash
make down    # stop containers, keep data
make reset   # stop containers and delete the kafka-data, postgres-data and minio-data volumes
```

Reset after changing `infra/postgres/init/` (the script only runs on an empty volume) or to start the demo from a clean registry.

## Troubleshooting

- Port already in use: another local PostgreSQL, MLflow or dev server is running, or macOS AirPlay holds port 5000. Copy `infra/env/.env.example` to `infra/env/.env` and set the matching `*_HOST_PORT` (for example `MLFLOW_HOST_PORT=5050`), then update the host-side URLs in the same file (`MLFLOW_TRACKING_URI`, `DATABASE_URL`, ...). Kafka keeps 9092 because its advertised listener is fixed.
- `mlflow` stays unhealthy: check `make logs s=mlflow`; the first start runs the database migrations and can take up to a minute.
- Kafka refuses to start after a version bump: `make reset` to drop the old log directory.
- MinIO no longer publishes images on Docker Hub or Quay. Compose and Kubernetes use `bitnamilegacy/minio`, which bundles the server, `mc` and `curl`.
