# 0009. Liveness probe without I/O
Status: Accepted
Date: 2026-10-21

## Context
The healthcheck of Compose polls the API every 30 seconds.

## Decision
- `GET /health` answers `200 {"status": "ok"}` as soon as the application serves requests, without database nor source, outside the API prefix, logged at `DEBUG` when it succeeds.

## Rejected alternatives
- A probe that reads the database or asks a source: a source that is down would restart a healthy container.

## Consequences
- A broken database shows in the errors of the routes, not in the probe.
