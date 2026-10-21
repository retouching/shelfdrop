"""HTTP errors of the uploads module."""

from shelfdrop.http.errors.errors import conflict, not_found, unprocessable, unprocessable_with
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode
from shelfdrop.uploads.types import Refusal


def upload_refused(reason: Refusal) -> ApiError:
    return unprocessable_with(ErrorCode.UPLOAD_REFUSED, "File refused", {"reason": reason})


def upload_not_found() -> ApiError:
    return not_found(ErrorCode.UPLOAD_NOT_FOUND, "Upload not found")


def upload_done() -> ApiError:
    return conflict(ErrorCode.UPLOAD_DONE, "Upload received already")


def chunk_refused() -> ApiError:
    return unprocessable(ErrorCode.CHUNK_REFUSED, "Chunk refused")


def upload_corrupt() -> ApiError:
    return unprocessable(ErrorCode.UPLOAD_CORRUPT, "The file has another SHA-256")
