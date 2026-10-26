# Continuous integration

| Workflow | Trigger | Checks |
|---|---|---|
| `ci.yml` | pull requests, pushes to `main` | One job per component, run only when its paths change, then `ci-gate` |
| `commit-lint.yml` | pull requests | Every commit message and the PR title against `.githooks/commit-msg` |
| `build-images.yml` | pull requests, pushes to `main`, tags `v*`, manual | Builds the image of every changed service; pushes to GHCR except on pull requests |

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
```
