# 0006. Rebase merge and linear history

Date: 2026-10-26. Status: accepted.

## Context

The project is evaluated partly on each member's contribution, which must stay visible and attributed in `main`. Squash merges collapse a branch into one commit authored by whoever merges; merge commits make history hard to bisect.

## Decision

`main` only accepts rebase merges, with linear history required by branch protection. Branches are rebased on `origin/main` before push, each commit follows `<type>(<scope>): <summary>` and builds on its own. Commit messages are checked by `.githooks/commit-msg` locally and by `commit-lint.yml` in CI. Branches are deleted on merge.

## Consequences

- Every commit keeps its author in `main`, and `git bisect` works on a straight line.
- Each commit must build and pass tests, not only the branch tip, so authors split work into atomic commits.
- Rebasing rewrites branch history; a branch shared by two people needs coordination before force-pushing.
