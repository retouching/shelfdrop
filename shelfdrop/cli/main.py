"""`shelfdrop`: the command line of the operator; for now the migration of the database."""

import argparse
import sys
from collections.abc import Sequence

from shelfdrop.config import Settings
from shelfdrop.db.migrate import upgrade_database
from shelfdrop.logging.setup import configure_logging


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="shelfdrop")
    commands = root.add_subparsers(dest="command", required=True)
    database = commands.add_parser("db", help="the database")
    actions = database.add_subparsers(dest="action", required=True)
    actions.add_parser("upgrade", help="apply every pending migration")
    return root


def main(arguments: Sequence[str] | None = None) -> int:
    parsed = parser().parse_args(arguments)
    settings = Settings()
    configure_logging(level=settings.log_level, json_format=settings.log_format == "json")
    if parsed.command == "db" and parsed.action == "upgrade":
        upgrade_database()
    return 0


if __name__ == "__main__":
    sys.exit(main())
