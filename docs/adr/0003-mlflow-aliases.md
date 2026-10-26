# 0003. MLflow aliases instead of stages

Date: 2026-10-26. Status: accepted.

## Context

The agent must promote a retrained model and roll back if needed, and fastapi-ml must always load the current production model. MLflow model stages (Staging, Production, Archived) are deprecated, and moving a stage touches several versions.

## Decision

The registered model `fraud-xgb` uses two aliases: `@champion` for the served version and `@challenger` for the candidate produced by a retrain. Consumers load `models:/fraud-xgb@champion`. Promotion moves `@champion` to the challenger's version and publishes `model.promoted` with the previous version; rollback moves the alias back. Stages are never used.

## Consequences

- Promotion and rollback are one API call each, and the previous version is kept in the `model.promoted` event.
- fastapi-ml reloads on `model.promoted` instead of polling the registry.
- Alias history is not kept by MLflow itself; the audit trail is the sequence of `model.promoted` events and the agent run tags on each version.
