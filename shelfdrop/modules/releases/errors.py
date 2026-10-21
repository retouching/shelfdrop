"""HTTP errors of the releases module."""

from shelfdrop.http.errors.errors import not_found, unavailable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def release_not_found() -> ApiError:
    return not_found(ErrorCode.RELEASE_NOT_FOUND, "Release not found")


def prowlarr_unavailable() -> ApiError:
    return unavailable(ErrorCode.PROWLARR_UNAVAILABLE, "Prowlarr does not answer")
