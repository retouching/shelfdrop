"""Helpers shared by the unit tests."""

from typing import Any, cast

from sqlalchemy.orm import Session


class NoSession:
    """A session no code may use: any access fails the test."""

    def __getattr__(self, name: str) -> Any:
        msg = f"the session must not be used (accessed {name})"
        raise AssertionError(msg)


def no_session() -> Session:
    # cast: the fake implements nothing; a fake repository built on it overrides every method.
    return cast("Session", NoSession())
