"""Logging configuration shared by the API and the CLI: one stderr handler, JSON or text, and
for the API and the placement worker a rotating file of JSON lines, read by the page."""

import logging
import logging.config
from pathlib import Path
from typing import Any, Final

from shelfdrop.logging.filters import RequestIdFilter
from shelfdrop.logging.formatters import JsonFormatter

TEXT_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
# A file of logs holds 5 MiB at most, then becomes `<name>.1` (the former `.1` becomes `.2`, the
# former `.2` is dropped): 15 MiB at most per process.
LOG_FILE_BYTES: Final = 5 * 1024 * 1024
LOG_FILE_BACKUPS: Final = 2


def log_file(directory: Path, process: str) -> Path:
    """The file of logs of a process (`api`, `placement`) in the directory of logs."""
    return directory / f"{process}.jsonl"


def configure_logging(*, level: str, json_format: bool, file: Path | None = None) -> None:
    """Replace any previous configuration (uvicorn's included); `level` is a stdlib level name.
    With `file`, the records go there too, always in JSON, its directory made if missing."""
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(config(level=level, json_format=json_format, file=file))


def config(*, level: str, json_format: bool, file: Path | None = None) -> dict[str, Any]:
    formatter: dict[str, Any] = (
        {"()": JsonFormatter}
        if json_format
        else {"format": TEXT_FORMAT, "defaults": {"request_id": "-"}}
    )
    # Below WARNING, SQLAlchemy logs SQL statements, their parameters and result rows; httpx logs
    # the address of every request at INFO and httpcore its connection trace at DEBUG: an address
    # may carry a key (a Discord webhook, a source that takes its key in the query string).
    library_level = max(logging.getLevelNamesMapping()[level], logging.WARNING)
    handlers: dict[str, Any] = {
        "stderr": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "default",
            "filters": ["request_id"],
        }
    }
    if file is not None:
        # The same records as stderr, so the same rules: never an address, a header, a body.
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(file),
            "maxBytes": LOG_FILE_BYTES,
            "backupCount": LOG_FILE_BACKUPS,
            "encoding": "utf-8",
            "formatter": "json",
            "filters": ["request_id"],
        }
    return {
        "version": 1,
        # Loggers created at import time (shelfdrop.*, uvicorn, sqlalchemy) must keep working.
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": RequestIdFilter},
        },
        "formatters": {"default": formatter, "json": {"()": JsonFormatter}},
        "handlers": handlers,
        "loggers": {
            # uvicorn installs its own handlers before calling the factory: route its records
            # to the root handler instead.
            "uvicorn": {"level": level, "handlers": [], "propagate": True},
            "uvicorn.error": {"level": level, "handlers": [], "propagate": True},
            # Replaced by AccessLogMiddleware: without handlers, uvicorn skips its access log.
            "uvicorn.access": {"handlers": [], "propagate": False},
            "sqlalchemy": {"level": library_level},
            "httpx": {"level": library_level},
            "httpcore": {"level": library_level},
        },
        "root": {"level": level, "handlers": list(handlers)},
    }
