"""Logging configuration shared by the API and the CLI: one stderr handler, JSON or text."""

import logging
import logging.config
from typing import Any, Final

from shelfdrop.logging.filters import RequestIdFilter
from shelfdrop.logging.formatters import JsonFormatter

TEXT_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"


def configure_logging(*, level: str, json_format: bool) -> None:
    """Replace any previous configuration (uvicorn's included); `level` is a stdlib level name."""
    logging.config.dictConfig(config(level=level, json_format=json_format))


def config(*, level: str, json_format: bool) -> dict[str, Any]:
    formatter: dict[str, Any] = (
        {"()": JsonFormatter}
        if json_format
        else {"format": TEXT_FORMAT, "defaults": {"request_id": "-"}}
    )
    # Below WARNING, SQLAlchemy logs SQL statements, their parameters and result rows; httpx logs
    # the address of every request at INFO and httpcore its connection trace at DEBUG: an address
    # may carry a key (a Discord webhook, a source that takes its key in the query string).
    library_level = max(logging.getLevelNamesMapping()[level], logging.WARNING)
    return {
        "version": 1,
        # Loggers created at import time (shelfdrop.*, uvicorn, sqlalchemy) must keep working.
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": RequestIdFilter},
        },
        "formatters": {"default": formatter},
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "default",
                "filters": ["request_id"],
            }
        },
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
        "root": {"level": level, "handlers": ["stderr"]},
    }
