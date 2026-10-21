"""HTTP exception carrying a machine-readable error code."""

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException

from shelfdrop.http.errors.types import ErrorCode


class ApiError(HTTPException):
    """Raise it for every HTTP error; handle_http_exception renders {"code", "detail", "data"}."""

    def __init__(
        self,
        status_code: int,
        *,
        code: ErrorCode,
        detail: str,
        data: dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code
        self.data = data
