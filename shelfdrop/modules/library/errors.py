"""HTTP errors of the library module."""

from shelfdrop.http.errors.errors import (
    not_found,
    unavailable,
    unprocessable,
    unprocessable_with,
)
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def series_not_found() -> ApiError:
    return not_found(ErrorCode.SERIES_NOT_FOUND, "Series not found")


def work_not_found() -> ApiError:
    return not_found(ErrorCode.WORK_NOT_FOUND, "Work not found")


def adoption_refused(reason: str, item_ids: tuple[str, ...]) -> ApiError:
    return unprocessable_with(
        ErrorCode.ADOPTION_REFUSED,
        "Adoption refused",
        {"reason": reason, "item_ids": list(item_ids)},
    )


def volume_not_found() -> ApiError:
    return not_found(ErrorCode.VOLUME_NOT_FOUND, "Volume not found")


def image_refused() -> ApiError:
    return unprocessable(ErrorCode.IMAGE_REFUSED, "Not a JPEG, a PNG or a WebP of 5 MB at most")


def jellyfin_unavailable() -> ApiError:
    return unavailable(ErrorCode.JELLYFIN_UNAVAILABLE, "Jellyfin is unavailable")
