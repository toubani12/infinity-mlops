# Infinity MLOps

Self-healing MLOps platform for real-time bank fraud detection.

Transactions are scored as they arrive. A drift monitor compares recent predictions with the reference data, and when quality degrades a LangGraph agent retrains the model, compares the challenger with the production champion and asks a human to approve the promotion. Nothing reaches production without that approval.

## Architecture

| Component | Stack | Path |
|---|---|---|
| backend-spring | Spring Boot 3, Java 21, PostgreSQL | `apps/backend-spring` |
| fastapi-ml | FastAPI, Python 3.12, XGBoost | `apps/fastapi-ml` |
| frontend-next | Next.js App Router, TypeScript | `apps/frontend-next` |
| drift-monitor | Evidently, Kubernetes CronJob | `services/drift-monitor` |
| agents-langgraph | LangGraph, Python 3.12 | `services/agents-langgraph` |
| pipelines | XGBoost, scikit-learn, MLflow | `pipelines` |
| platform | Kafka KRaft, MLflow, MinIO, PostgreSQL, Kustomize | `infra`, `k8s` |

Services talk through Kafka topics whose JSON Schemas live in `libs/contracts/events`. The dashboard calls the Spring backend over REST and SSE, and the inference service reads the MLflow registry to load the current `@champion`.

## Team

| Member | Role | Scope |
|---|---|---|
| Badr Eddine Toubani (@toubani12) | Lead, platform and integration | contracts, infra, k8s, CI, agent, docs |
| @Agrigah | Developer / MLOps engineer | pipelines, inference, drift, retrain job |
| @mustapha005 | Full-stack / backend engineer | Spring API, dashboard, approval flow |

## Getting started

```bash
git clone git@github.com:toubani12/infinity-mlops.git && cd infinity-mlops
git config core.hooksPath .githooks
git config pull.rebase true
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for branches, commit format and the pull request flow.
