"""Database engine and session factories, registered in shelfdrop/container.py (no wireup here)."""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from shelfdrop.config import Settings


def configure_connection(connection: Any, _: object) -> None:
    """Every SQLite connection: WAL (readers never wait for the writer), foreign keys on, and a
    writer waits 5 seconds for another one instead of failing at once."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def new_engine(url: str, *, single_connection: bool = False) -> Engine:
    """`single_connection`: no pool, for Alembic, which opens one connection and closes it."""
    # hide_parameters: SQL parameters never appear in exception messages (and so in logs).
    if single_connection:
        engine = create_engine(url, hide_parameters=True, poolclass=NullPool)
    else:
        engine = create_engine(url, hide_parameters=True)
    event.listen(engine, "connect", configure_connection)
    return engine


def open_engine(settings: Settings) -> Iterator[Engine]:
    """The engine of the process (a container singleton), disposed when the container closes."""
    engine = new_engine(settings.database_url)
    try:
        yield engine
    finally:
        engine.dispose()


def open_session(engine: Engine) -> Iterator[Session]:
    """One session per container scope (an HTTP request, a CLI operation); it never commits."""
    with Session(engine, expire_on_commit=False) as session:
        yield session
