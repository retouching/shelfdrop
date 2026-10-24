# 0005. SQLite, SQLAlchemy and Alembic
Status: Accepted
Date: 2026-10-21

## Context
Decided at the start of the project: a SQLite database, its schema through SQLAlchemy models and Alembic revisions.

## Decision
- One SQLite file, `shelfdrop.db`, in `SHELFDROP_DATA_DIR`; every connection in WAL mode, with the foreign keys on and a 5 second wait for a writer.
- SQLAlchemy 2, synchronous, one session per request, never committing by itself; queries in `repository.py` files and `shelfdrop/db/` alone (ruff `TID251`).
- Alembic revisions in `shelfdrop/db/migrations/versions/`, generated against the models, in batch mode (SQLite copies a table to alter it); a pushed revision never changes (`tests/unit/db/test_migrate.py` pins the digest of each). The container applies them at start (`shelfdrop db upgrade`).

## Rejected alternatives
- Plain SQL files numbered by hand and `PRAGMA user_version`: the first version of shelfdrop; no comparison of the schema with the models, and a migration written by hand for every change.
- PostgreSQL: one more service for one small application on one machine.

## Consequences
- The routes that wait on the network are `async` and run the repository in the threadpool (ADR 0007).

## Replaced
- The numbered SQL files of `shelfdrop/db/migrations/*.sql`, applied by a hand-made runner: replaced by Alembic before any deployment.
