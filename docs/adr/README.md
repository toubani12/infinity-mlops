# Architecture decision records

One file per structuring decision: context, decision, consequences. A decision is never edited after it is accepted; a new ADR supersedes it.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-monorepo.md) | Single monorepo with path-filtered CI | Accepted |
| [0002](0002-kafka-kraft.md) | Kafka in KRaft mode, one broker locally | Accepted |
| [0003](0003-mlflow-aliases.md) | MLflow aliases `@champion` / `@challenger` instead of stages | Accepted |
| [0004](0004-retrain-kubernetes-job.md) | Retraining runs as a Kubernetes Job launched by the agent | Accepted |
| [0005](0005-kustomize-overlays.md) | Kustomize base with `minikube` and `ci-kind` overlays | Accepted |
| [0006](0006-rebase-merge-linear-history.md) | Rebase merge and linear history on `main` | Accepted |
| [0007](0007-rules-only-agent.md) | Rules decide in the agent, an optional LLM only explains | Accepted |
| [0008](0008-transactional-outbox-backend.md) | Transactional outbox for `transaction.raw` in the backend | Accepted |
| [0009](0009-prediction-log-minio-hourly.md) | Prediction log on MinIO, partitioned by scoring hour | Accepted |
