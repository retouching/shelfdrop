"""HTTP errors of the settings module."""

from shelfdrop.http.errors.errors import unprocessable_with
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def invalid_settings(keys: list[str]) -> ApiError:
    return unprocessable_with(ErrorCode.INVALID_SETTINGS, "Invalid settings", {"keys": keys})
