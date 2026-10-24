"""HTTP errors of the account module."""

from shelfdrop.http.errors.errors import conflict, not_found, unprocessable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def account_exists() -> ApiError:
    return conflict(ErrorCode.ACCOUNT_EXISTS, "The internal account exists")


def account_not_found() -> ApiError:
    return not_found(ErrorCode.ACCOUNT_NOT_FOUND, "No internal account")


def password_refused() -> ApiError:
    return unprocessable(ErrorCode.PASSWORD_REFUSED, "Password refused")
