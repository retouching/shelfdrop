"""HTTP errors of the searches module."""

from shelfdrop.http.errors.errors import not_found, unavailable, unprocessable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def search_not_found() -> ApiError:
    return not_found(ErrorCode.SEARCH_NOT_FOUND, "Search not found")


def query_too_short() -> ApiError:
    return unprocessable(ErrorCode.QUERY_TOO_SHORT, "The search needs 2 letters or digits")


def too_many_names() -> ApiError:
    return unprocessable(ErrorCode.TOO_MANY_NAMES, "A work is searched under 6 names at most")


def prowlarr_unavailable() -> ApiError:
    return unavailable(ErrorCode.PROWLARR_UNAVAILABLE, "Prowlarr does not answer")
