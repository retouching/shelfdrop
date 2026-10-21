"""The OpenAPI document of the API and its page (ADR 0021), for the session of an administrator:
`/api/v1/openapi.json` and `/api/docs`. Neither is in the document itself."""

from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from shelfdrop.http.openapi import docs_page

router = APIRouter(tags=["docs"], include_in_schema=False)


@router.get("/v1/openapi.json")
async def read_openapi(request: Request) -> dict[str, Any]:
    schema: dict[str, Any] = request.app.openapi()
    return schema


@router.get("/docs", response_class=HTMLResponse)
async def read_docs(request: Request) -> HTMLResponse:
    return HTMLResponse(docs_page(request.app.openapi()))
