"""Schema migrations: apply the Alembic revisions of shelfdrop/db/migrations."""

from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR: Final = Path(__file__).resolve().parent / "migrations"


def upgrade_database() -> None:
    """Apply every pending Alembic revision; the URL comes from Settings (see migrations/env.py)."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("path_separator", "os")
    command.upgrade(config, "head")
