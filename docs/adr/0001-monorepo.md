# 0001. Single monorepo

Date: 2026-10-26. Status: accepted.

## Context

Three engineers build six components that share event contracts. Contracts change in the first sprints, and a change must reach every producer and consumer in the same review. Separate repositories would need a published contracts package, version bumps in each consumer and three PR queues to follow.

## Decision

One repository, `infinity-mlops`. User-facing applications live in `apps/`, internal services in `services/`, shared code in `libs/`, training code in `pipelines/`, deployment in `infra/` and `k8s/`. CI uses `dorny/paths-filter` so a PR only runs the jobs of the folders it touches, and a single `ci-gate` job is the required check. `CODEOWNERS` maps each folder to its owner.

## Consequences

- A contract change and its consumers' updates land in one PR, reviewed once.
- Each Python service keeps its own `pyproject.toml` and `uv.lock`, so dependencies stay isolated despite the shared repository.
- CI cost grows with the number of components unless path filters are kept accurate; changes under `libs/contracts/` deliberately run every consumer.
- Clones are larger and every member sees every folder; access cannot be restricted per component.
