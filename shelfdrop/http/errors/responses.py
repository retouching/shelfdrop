"""JSON error responses: the only place that builds an error body."""

from collections.abc import Mapping
from typing import Any

from fastapi import status
from starlette.responses import JSONResponse

from shelfdrop.http.errors.schemas import ErrorResponse
from shelfdrop.http.errors.types import ErrorCode


def error_response(
    status_code: int,
    code: ErrorCode,
    detail: str,
    *,
    data: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(code=code, detail=detail, data=data)
    return JSONResponse(body.model_dump(mode="json"), status_code=status_code, headers=headers)


def internal_error_response() -> JSONResponse:
    """Generic 500: never the exception message, type or traceback (they stay in the logs)."""
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, ErrorCode.INTERNAL_ERROR, "Internal Server Error"
    )
