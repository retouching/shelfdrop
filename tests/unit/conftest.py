"""Fixtures shared by the unit tests."""

import logging
from collections.abc import Iterator

import pytest


def all_loggers() -> list[logging.Logger]:
    registered = logging.Logger.manager.loggerDict.values()
    return [logging.getLogger()] + [
        logger for logger in registered if isinstance(logger, logging.Logger)
    ]


@pytest.fixture
def isolated_logging() -> Iterator[None]:
    """Undo configure_logging() (dictConfig): it replaces handlers and levels process-wide."""
    saved = {
        logger: (
            logger.level,
            logger.propagate,
            logger.disabled,
            list(logger.handlers),
            list(logger.filters),
        )
        for logger in all_loggers()
    }
    try:
        yield
    finally:
        for logger in all_loggers():
            level, propagate, disabled, handlers, filters = saved.get(
                logger, (logging.NOTSET, True, False, [], [])
            )
            logger.setLevel(level)
            logger.propagate = propagate
            logger.disabled = disabled
            logger.handlers[:] = handlers
            logger.filters[:] = filters
