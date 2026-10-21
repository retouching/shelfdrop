# 0002. English, Conventional Commits, branch master
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user: commits pushed to `git.oh.rip/sylvain/shelfdrop` carry his name alone, with no co-author line; regular commits, a push every 9 commits; the rules of medusa for the rest.

## Decision
- Code, comments, logs, API messages and docs in English; the visible texts in French (ADR 0008).
- Conventional Commits in English, small and focused, each passing the gates; no `Co-authored-by`, no `Signed-off-by`, no mention of a tool.
- Default branch `master`. A push gathers about 9 commits. The version of `pyproject.toml` starts at `0.1.0`.

## Rejected alternatives
- `main`: the other repositories of the forge use `master`.

## Consequences
- `.githooks/pre-push` runs the gates before each push.
