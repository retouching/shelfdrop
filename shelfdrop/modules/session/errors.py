"""HTTP errors of the session module."""

from shelfdrop.http.errors.errors import too_many_requests, unauthorized, unavailable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def login_refused() -> ApiError:
    return unauthorized(ErrorCode.LOGIN_REFUSED, "Login refused")


def too_many_attempts() -> ApiError:
    return too_many_requests(ErrorCode.TOO_MANY_ATTEMPTS, "Too many attempts")


def jellyfin_unavailable() -> ApiError:
    return unavailable(ErrorCode.JELLYFIN_UNAVAILABLE, "Jellyfin does not answer")
