# Continuous integration

| Workflow | Trigger | Checks |
|---|---|---|
| `ci.yml` | pull requests, pushes to `main` | One job per component, run only when its paths change, then `ci-gate` |
| `commit-lint.yml` | pull requests | Every commit message and the PR title against `.githooks/commit-msg` |
| `build-images.yml` | pull requests, pushes to `main`, tags `v*`, manual | Builds the image of every changed service; pushes to GHCR except on pull requests |
| `e2e-kind.yml` | pushes to `main`, manual | Builds every image, deploys `k8s/overlays/ci-kind` on a kind cluster and runs `scripts/e2e/demo-short.sh` |

## Path filters

| Job | Runs when these change |
|---|---|
| `contracts` | `libs/contracts/**` |
| `fastapi-ml` | `apps/fastapi-ml/**`, `libs/contracts/**` |
| `drift-monitor` | `services/drift-monitor/**`, `libs/contracts/**` |
| `agents-langgraph` | `services/agents-langgraph/**`, `libs/contracts/**` |
| `pipelines` | `pipelines/**` |
| `backend-spring` | `apps/backend-spring/**`, `libs/contracts/**` |
| `frontend-next` | `apps/frontend-next/**` |
| `k8s` | `k8s/**` (renders the base and both overlays with `kubectl kustomize`) |

A change to `ci.yml` or `.github/actions/` runs every job. Python jobs run `uv sync --frozen`, `ruff check`, `ruff format --check` and `pytest -q` through `.github/actions/uv-checks`. A job whose folder has no `pyproject.toml`, `pom.xml` or `package-lock.json` yet passes with a notice.

## Images

`build-images.yml` builds `ghcr.io/toubani12/infinity-mlops/<service>` for `backend-spring`, `fastapi-ml`, `frontend-next`, `agents-langgraph`, `drift-monitor`, `pipelines` and `mlflow` (from `infra/mlflow`). The build context is the service folder.

| Event | Services built | Tags pushed |
|---|---|---|
| pull request | changed folders | none, build only |
| push to `main` | changed folders | full commit SHA, `latest` |
| tag `v1.2.3` | all | full commit SHA, `1.2.3` |
| manual run | all | full commit SHA, `latest` when run on `main` |

A service whose folder has no `Dockerfile` yet is skipped with a notice. Layers are cached per service in the GitHub Actions cache. Packages are private by default: make each one public in its GHCR settings, or create an image pull secret, before a cluster pulls from GHCR.

## End-to-end on kind

`e2e-kind.yml` builds the seven images with `docker buildx` (reusing the layers `build-images.yml` cached), tags them `:ci` (plus `pipelines:latest`, the tag the retrain Job template names), loads them into a kind cluster with `kind load docker-image`, applies `k8s/overlays/ci-kind` and runs the short scenario:

1. waits for Kafka, PostgreSQL, MinIO, MLflow, the backend, fastapi-ml and the agent;
2. runs the Job `e2e-bootstrap-champion` (pipelines image): 60 000 synthetic rows go to `s3://datasets/raw/creditcard.parquet`, and a deliberately weak champion is trained on a separate 6 000-row sample, so the retrain has something to beat (`registry.promote` resets `@champion` to it when an earlier run left a stronger one);
3. port-forwards the backend, fastapi-ml and MLflow, gets an admin dev token, posts 20 transactions and waits until each has a `fraudScore`;
4. publishes the `drift.detected` contract example with a fresh `report_id` through `kafka-0`, waits for the agent run to reach `AWAITING_APPROVAL` (the agent's retrain Job takes about a minute), approves it through `POST /api/agent/runs/{runId}/approve`;
5. checks the run is `PROMOTED`, that MLflow `@champion` is the promoted version and that fastapi-ml `/model` serves it.

On failure the workflow prints pods, events and the logs of the services and Jobs. The same script runs locally against minikube:

```bash
make minikube
make e2e-demo        # bash scripts/e2e/demo-short.sh
```

It needs `kubectl`, `curl` and `jq`, and refuses to start while an agent run is still open (one retrain at a time). Overrides: `NAMESPACE`, `PIPELINES_IMAGE`, `TRANSACTIONS`, `ROLLOUT_TIMEOUT`, `STEP_TIMEOUT`, `RUN_TIMEOUT`, `BACKEND_PORT` (18080), `INFERENCE_PORT` (18000), `MLFLOW_PORT` (15000).

## Required checks

`ci-gate` passes when every job succeeded or was skipped by the filter, and fails on any failure or cancellation. Make it and `commit-lint` the only required checks, once both have run on `main`:

```bash
gh api -X PATCH repos/toubani12/infinity-mlops/branches/main/protection/required_status_checks \
  -F strict=true -f 'contexts[]=ci-gate' -f 'contexts[]=commit-lint'
```

## Run the same checks locally

```bash
make lint
make test
actionlint            # https://github.com/rhysd/actionlint, validates the workflow files
shellcheck scripts/*.sh scripts/e2e/*.sh
```
