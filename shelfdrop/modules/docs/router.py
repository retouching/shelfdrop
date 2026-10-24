"""The public OpenAPI document of the API and its page (ADR 0021), for a session or any access
token: `/api/v1/openapi.json` and `/api/docs`, the Swagger UI of the front-end build. Neither is in
the document itself."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import FileResponse

from shelfdrop.http.errors.errors import not_found
from shelfdrop.http.errors.types import ErrorCode

# The page of the build that shows the document (web/swagger/index.html).
PAGE = Path("swagger") / "index.html"


def docs_router(static_dir: Path) -> APIRouter:
    """The router of the document and of its page, read from the front-end built in
    `static_dir`; the page answers 404 without the build."""
    page = static_dir.resolve() / PAGE
    router = APIRouter(tags=["docs"], include_in_schema=False)

    @router.get("/v1/openapi.json")
    async def read_openapi(request: Request) -> dict[str, Any]:
        schema: dict[str, Any] = request.app.public_openapi()
        return schema

    @router.get("/docs")
    async def read_docs() -> FileResponse:
        if not page.is_file():
            raise not_found(ErrorCode.NOT_FOUND, "Not Found")
        return FileResponse(page, media_type="text/html")

    return router
