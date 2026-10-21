"""HTTP errors of the trackers module."""

from shelfdrop.http.errors.errors import unavailable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def prowlarr_unavailable() -> ApiError:
    return unavailable(ErrorCode.PROWLARR_UNAVAILABLE, "Prowlarr does not answer")
