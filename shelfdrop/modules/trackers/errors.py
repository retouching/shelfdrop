"""HTTP errors of the trackers module."""

from shelfdrop.http.errors.errors import unavailable, unprocessable_with
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def prowlarr_unavailable() -> ApiError:
    return unavailable(ErrorCode.PROWLARR_UNAVAILABLE, "Prowlarr does not answer")


def unknown_tracker_category(indexer_ids: list[int]) -> ApiError:
    return unprocessable_with(
        ErrorCode.UNKNOWN_TRACKER_CATEGORY,
        "A tracker is given a category it does not know",
        {"indexer_ids": indexer_ids},
    )
