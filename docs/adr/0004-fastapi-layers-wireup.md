# 0004. FastAPI, layers and wireup
Status: Accepted
Date: 2026-10-21

## Context
Decided at the start of the project. A route must stay thin, the rules must be testable without HTTP nor database, and the composition must live in one place.

## Decision
- FastAPI on uvicorn. HTTP features in `shelfdrop/modules/<feature>/` (`router.py`, `schemas.py`, `errors.py`); domains directly under `shelfdrop/` (`works/`: service, repository, types, exceptions, pure rules, clients).
- A router calls its service and maps its domain exceptions to HTTP errors; a service holds the rules and commits last through its repository; a repository is the only place for queries.
- wireup builds the services and repositories, scoped to a request; `shelfdrop/container.py` is the one list of registrations; only the composition, `release_session` and the routers import wireup (`tests/unit/test_layers.py`).
- No name starts with an underscore (`tests/unit/test_naming.py`).

## Rejected alternatives
- `app.state` and hand-made dependencies: the composition spreads across the routes.
- Services that receive the `Request`: they could not be tested without HTTP.

## Consequences
- A service is tested with fakes that subclass its repository.
