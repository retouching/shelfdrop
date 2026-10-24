"""HTTP errors of the downloads module."""

from shelfdrop.http.errors.errors import conflict, not_found, unprocessable_with
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def search_not_found() -> ApiError:
    return not_found(ErrorCode.SEARCH_NOT_FOUND, "Search not found")


def release_not_in_search(ids: list[str]) -> ApiError:
    return unprocessable_with(
        ErrorCode.RELEASE_NOT_IN_SEARCH, "Releases not in the search", {"ids": ids}
    )


def release_not_automatic(ids: list[str]) -> ApiError:
    return unprocessable_with(
        ErrorCode.RELEASE_NOT_AUTOMATIC,
        "Releases an automatic download may not take",
        {"ids": ids},
    )


def download_not_found() -> ApiError:
    return not_found(ErrorCode.DOWNLOAD_NOT_FOUND, "Download not found")


def download_not_retryable() -> ApiError:
    return conflict(ErrorCode.DOWNLOAD_NOT_RETRYABLE, "Only a torrent not received is sent again")


def download_cover_not_found() -> ApiError:
    return not_found(ErrorCode.DOWNLOAD_COVER_NOT_FOUND, "No cover for this download")
