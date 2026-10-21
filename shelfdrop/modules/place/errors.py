"""HTTP errors of the place module (the page Ranger)."""

from shelfdrop.http.errors.errors import conflict, not_found, unprocessable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def item_not_found() -> ApiError:
    return not_found(ErrorCode.PLACE_ITEM_NOT_FOUND, "File to place not found")


def item_busy() -> ApiError:
    return conflict(ErrorCode.PLACE_ITEM_BUSY, "File placed, or being placed")


def request_refused() -> ApiError:
    return unprocessable(ErrorCode.PLACE_REQUEST_REFUSED, "Request does not fit the file")
