# 0004. Retraining as a Kubernetes Job launched by the agent

Date: 2026-10-26. Status: accepted.

## Context

Retraining is triggered by the agent after a real drift is qualified. GitHub Actions runners cannot reach a local minikube, MLflow or MinIO, and the training data lives next to the cluster. Letting the agent run arbitrary commands would break the closed tool list.

## Decision

The agent creates a Job from the template `k8s/jobs/retrain-job.yaml`, parameterised by data window and training config, using the `pipelines` image. Its ServiceAccount can only create, get and list Jobs in namespace `infinity`. Only one retrain Job runs at a time; an alert that arrives during a run is attached to that run. The Job registers its model with the alias `@challenger`.

## Consequences

- Training runs next to MLflow and MinIO with cluster DNS and secrets, and the same template works on minikube and kind.
- The agent's blast radius is limited to Jobs in one namespace; there is no shell or free `kubectl`.
- The agent must poll the Job status and handle timeouts and failed pods itself.
- Under Docker Compose there is no Job API; retraining outside Kubernetes means running the pipelines training entry point by hand.
