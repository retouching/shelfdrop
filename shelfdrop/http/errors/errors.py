"""Generic HTTP error factories: the only place that constructs an ApiError (ADR 0006).

A feature's errors.py holds one factory per code of its own, which calls one of these with its
message written in the function.
"""

from collections.abc import Sequence
from typing import Any

from fastapi import status

from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode, FieldError


def not_found(code: ErrorCode, detail: str) -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, code=code, detail=detail)


def unprocessable(code: ErrorCode, detail: str) -> ApiError:
    """422 with a code of its own: what the request carries is well formed and refused."""
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, code=code, detail=detail)


def unavailable(code: ErrorCode, detail: str) -> ApiError:
    """503 without `Retry-After`: something the API relays to does not answer."""
    return ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, code=code, detail=detail)


def unprocessable_with(code: ErrorCode, detail: str, data: dict[str, Any]) -> ApiError:
    """422 with a code of its own and the details of what is refused."""
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, code=code, detail=detail, data=data)


def validation_failed(errors: Sequence[FieldError]) -> ApiError:
    """422 `validation_failed`; `handle_request_validation_error` answers through it too."""
    return ApiError(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        code=ErrorCode.VALIDATION_FAILED,
        detail="Request validation failed",
        data={
            "errors": [
                {"type": error.type, "loc": list(error.loc), "msg": error.msg} for error in errors
            ]
        },
    )
