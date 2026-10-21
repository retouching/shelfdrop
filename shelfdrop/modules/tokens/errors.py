"""HTTP errors of the tokens module."""

from shelfdrop.http.errors.errors import not_found
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def token_not_found() -> ApiError:
    return not_found(ErrorCode.TOKEN_NOT_FOUND, "Token not found")
