"""Alembic environment: migrations always run online against Settings().database_url."""

from alembic import context

import shelfdrop.db.models  # noqa: F401 -- registers every model on Base.metadata
from shelfdrop.config import Settings
from shelfdrop.db.base import Base
from shelfdrop.db.engine import new_engine


def run_migrations_online() -> None:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = new_engine(settings.database_url, single_connection=True)
    try:
        with engine.connect() as connection:
            # render_as_batch: SQLite alters a table by copying it.
            context.configure(
                connection=connection, target_metadata=Base.metadata, render_as_batch=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    msg = "Offline (--sql) migrations are not supported."
    raise RuntimeError(msg)
run_migrations_online()
