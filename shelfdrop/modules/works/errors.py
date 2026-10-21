"""HTTP errors of the works module."""

from shelfdrop.http.errors.errors import not_found, unavailable, unprocessable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def work_not_found() -> ApiError:
    return not_found(ErrorCode.WORK_NOT_FOUND, "Work not found")


def query_too_short() -> ApiError:
    return unprocessable(ErrorCode.QUERY_TOO_SHORT, "The search needs 2 letters or digits")


def sources_unavailable() -> ApiError:
    return unavailable(ErrorCode.SOURCES_UNAVAILABLE, "No metadata source answered")
