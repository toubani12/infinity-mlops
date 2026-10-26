# Contributing

## Branches

- `main` is protected and only receives rebase merges.
- One branch per deliverable, named `feat/<topic>` or `fix/<topic>` as planned in the sprint board.
- Start from an up-to-date `main` and rebase on `origin/main` before every push.

## Commits

Format, in English, imperative, lowercase, no final period:

```
<type>(<scope>): <summary of 72 characters max>
```

Types: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`, `ci`, `chore`.

Scopes: `contracts`, `infra`, `k8s`, `agent`, `pipelines`, `training`, `registry`, `inference`, `drift`, `api`, `messaging`, `alerts`, `security`, `web`, `adr`.

The body is optional and explains why. The footer references the issue: `Refs #42` or `Closes #42`.

The `commit-msg` hook in `.githooks/` checks the header and rejects tool attribution lines. Enable it once per clone with `git config core.hooksPath .githooks`. CI runs the same check on every commit of a pull request.

## Code comments

Write a comment only when the code cannot say why: a business rule, a workaround for a library bug with a link to the issue. Comments that paraphrase the next line, filler docstrings and decorative headers are rejected in review.

## Pull requests

1. An issue exists in the sprint milestone and is assigned.
2. The PR title follows the commit format and the template is filled in.
3. `ci-gate` and `commit-lint` are green.
4. A code owner approves: Badr for members' PRs, the folder owner for Badr's PRs.
5. Badr merges with rebase; the branch is deleted automatically.

Keep PRs under 400 changed lines. Reviews happen within one working day.
