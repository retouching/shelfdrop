"""HTTP errors of the setup module."""

from shelfdrop.http.errors.errors import conflict, not_found
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def setup_done() -> ApiError:
    return conflict(ErrorCode.SETUP_DONE, "Setup done")


def account_exists() -> ApiError:
    return conflict(ErrorCode.ACCOUNT_EXISTS, "The internal account exists")


def jellyfin_not_connected() -> ApiError:
    return conflict(ErrorCode.JELLYFIN_NOT_CONNECTED, "Jellyfin is not connected")


def account_not_found() -> ApiError:
    return not_found(ErrorCode.ACCOUNT_NOT_FOUND, "No internal account")
