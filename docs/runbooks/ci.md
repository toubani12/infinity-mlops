# Continuous integration

| Workflow | Trigger | Checks |
|---|---|---|
| `ci.yml` | pull requests, pushes to `main` | One job per component, run only when its paths change, then `ci-gate` |
| `commit-lint.yml` | pull requests | Every commit message and the PR title against `.githooks/commit-msg` |

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

A change to `ci.yml` or `.github/actions/` runs every job. Python jobs run `uv sync --frozen`, `ruff check`, `ruff format --check` and `pytest -q` through `.github/actions/uv-checks`. A job whose folder has no `pyproject.toml`, `pom.xml` or `package-lock.json` yet passes with a notice.

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
