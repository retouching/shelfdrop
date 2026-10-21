"""Exception handlers registered by shelfdrop.main: every error body is {"code", "detail",
"data"}."""

from typing import Final

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from shelfdrop.http.errors.errors import validation_failed
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.responses import error_response, internal_error_response
from shelfdrop.http.errors.types import ErrorCode, FieldError

# Codes of the HTTP errors raised by Starlette/FastAPI themselves (not ApiError).
FRAMEWORK_CODES: Final[dict[int, ErrorCode]] = {
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
}


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """ApiError keeps its code and data; other HTTP errors get a code from their status."""
    if isinstance(exc, ApiError):
        code, data = exc.code, exc.data
    else:
        code, data = FRAMEWORK_CODES.get(exc.status_code, ErrorCode.HTTP_ERROR), None
    # exc.headers carries WWW-Authenticate (401) and Allow (405).
    return error_response(exc.status_code, code, str(exc.detail), data=data, headers=exc.headers)


async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 without `input` nor `ctx`: they echo client values, which may be secrets."""
    error = validation_failed(
        [
            FieldError(loc=tuple(item["loc"]), msg=item["msg"], type=item["type"])
            for item in exc.errors()
        ]
    )
    return await handle_http_exception(request, error)


async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Exceptions raised outside UnhandledErrorsMiddleware; uvicorn still logs them."""
    return internal_error_response()
