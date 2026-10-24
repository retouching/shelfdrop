"""HTTP errors of the library module."""

from shelfdrop.http.errors.errors import not_found, unavailable, unprocessable
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def series_not_found() -> ApiError:
    return not_found(ErrorCode.SERIES_NOT_FOUND, "Series not found")


def volume_not_found() -> ApiError:
    return not_found(ErrorCode.VOLUME_NOT_FOUND, "Volume not found")


def image_refused() -> ApiError:
    return unprocessable(ErrorCode.IMAGE_REFUSED, "Not a JPEG, a PNG or a WebP of 5 MB at most")


def jellyfin_unavailable() -> ApiError:
    return unavailable(ErrorCode.JELLYFIN_UNAVAILABLE, "Jellyfin is unavailable")
