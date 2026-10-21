"""Response schema shared by every error."""

from typing import Any

from pydantic import BaseModel

from shelfdrop.http.errors.types import ErrorCode


class ErrorResponse(BaseModel):
    """Body of every error response; `data` holds structured details or null."""

    code: ErrorCode
    detail: str
    data: dict[str, Any] | None
