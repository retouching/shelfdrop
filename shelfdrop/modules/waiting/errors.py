"""HTTP errors of the waiting module."""

from shelfdrop.http.errors.errors import not_found
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def waiting_not_found() -> ApiError:
    return not_found(ErrorCode.WAITING_NOT_FOUND, "Waiting search not found")
