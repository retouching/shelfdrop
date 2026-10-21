# 0003. Python 3.13 and uv
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user: the stack of medusa.

## Decision
- Python 3.13 (`requires-python = ">=3.13"`, `.python-version`), a flat layout built by `uv_build`, the dependencies and the tools locked in `uv.lock`.
- ruff (lint and format), mypy strict with the pydantic plugin, pytest 9 in strict mode with warnings as errors.
- The image builds from `uv.lock` (`uv sync --locked`), without BuildKit, so that the plain builder of a host builds it.

## Rejected alternatives
- pip and requirements files: no lock of the transitive dependencies.

## Consequences
- `uv add` changes `pyproject.toml` and `uv.lock` together; both are committed with the change.
