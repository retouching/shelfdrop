"""The OpenAPI document of the API (ADR 0021): the schema FastAPI builds from the routes, with who
may call each operation (the session, an access token and its scope), the error body of every
refusal, and a page that shows it. `python -m shelfdrop.openapi` writes it to docs/openapi.json.
"""

import html
import json
from collections.abc import Callable
from typing import Any, Final, Literal, override

from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute

from shelfdrop.http.dependencies import (
    READS,
    SESSION_COOKIE,
    require_access,
    require_reader,
    require_session,
)
from shelfdrop.http.errors.schemas import ErrorResponse

type Access = Literal["public", "session", "read", "write"]

ERROR_REF: Final = {"$ref": "#/components/schemas/ErrorResponse"}
SECURITY_SCHEMES: Final = {
    "session": {
        "type": "apiKey",
        "in": "cookie",
        "name": SESSION_COOKIE,
        "description": "The session of an administrator of Jellyfin, opened by "
        "`POST /api/v1/session`. A write needs the `Origin` of the host.",
    },
    "token": {
        "type": "http",
        "scheme": "bearer",
        "description": "An access token (`sd_...`) created on the page Paramètres, API et MCP. "
        "`read` reads; `write` also downloads, places files and keeps searches waiting. "
        "60 requests a minute; never the settings nor the tokens. No `Origin` needed.",
    },
}
DESCRIPTION: Final = (
    "The API of shelfdrop: the work search, the releases of Prowlarr, the downloads, Ranger, "
    "the waiting searches. A browser signs in with the session cookie; a program sends "
    "`Authorization: Bearer <token>`. Each operation names the access it needs in "
    "`x-access`: `public`, `session` (the cookie alone), `read` (the cookie or any token), "
    "`write` (the cookie or a token `write`). Every error body is "
    '`{"code", "detail", "data"}`; the codes are listed in the schema `ErrorResponse`.'
)
REFUSALS: Final[dict[Access, dict[str, str]]] = {
    "public": {},
    "session": {
        "401": "No session (`not_signed_in`).",
        "403": "A write from another origin (`origin_refused`), or an access token "
        "(`token_forbidden`).",
    },
    "read": {
        "401": "No session, or a token unknown, expired or revoked (`not_signed_in`).",
        "429": "More than 60 requests in a minute with this token (`too_many_requests`).",
    },
    "write": {
        "401": "No session, or a token unknown, expired or revoked (`not_signed_in`).",
        "403": "A write from another origin with the cookie (`origin_refused`), or a token "
        "of reading (`token_forbidden`).",
        "429": "More than 60 requests in a minute with this token (`too_many_requests`).",
    },
}
SECURITY: Final[dict[Access, list[dict[str, list[str]]]]] = {
    "public": [],
    "session": [{"session": []}],
    "read": [{"session": []}, {"token": []}],
    "write": [{"session": []}, {"token": []}],
}


def access_of(route: APIRoute, method: str, guard: Callable[..., Any] | None) -> Access:
    """Who may call this operation: from the guard build_app() puts on its router, else from
    the one the route asks for itself."""
    calls = {guard} if guard is not None else set()
    calls |= {d.call for d in route.dependant.dependencies if d.call is not None}
    if require_session in calls:
        return "session"
    if require_reader in calls:
        return "read"
    if require_access in calls:
        return "read" if method in READS else "write"
    return "public"


def describe(schema: dict[str, Any], accesses: dict[tuple[str, str], Access]) -> dict[str, Any]:
    """The schema of FastAPI, with the access of each operation, its refusals, and the error body
    instead of the validation error FastAPI describes (the API never answers it)."""
    schema["info"]["description"] = DESCRIPTION
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    schemas["ErrorResponse"] = ErrorResponse.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    components["securitySchemes"] = SECURITY_SCHEMES
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            access = accesses[(path, method)]
            operation["x-access"] = access
            operation["security"] = SECURITY[access]
            responses = operation.setdefault("responses", {})
            if "422" in responses:
                responses["422"] = {
                    "description": "The request does not match the schema "
                    "(`validation_failed`), or a code of the operation.",
                    "content": {"application/json": {"schema": ERROR_REF}},
                }
            for status, text in REFUSALS[access].items():
                responses.setdefault(
                    status,
                    {"description": text, "content": {"application/json": {"schema": ERROR_REF}}},
                )
    return schema


class DocumentedApi(FastAPI):
    """The application, whose `openapi()` is the document of ADR 0021: served at
    `/api/v1/openapi.json` and `/api/docs` to the session of an administrator, written to
    docs/openapi.json. Its routers come through `include`, which keeps who may call each
    operation."""

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.accesses: dict[tuple[str, str], Access] = {}

    def include(
        self, router: APIRouter, *, prefix: str = "", guard: Callable[..., Any] | None = None
    ) -> None:
        """Include `router` under `prefix`, every route behind `guard` (`require_session`,
        `require_reader`, `require_access`; None: the routes ask for themselves)."""
        for route in router.routes:
            if isinstance(route, APIRoute):
                for method in route.methods or ():
                    key = (prefix + route.path_format, method.lower())
                    self.accesses[key] = access_of(route, method, guard)
        dependencies = [] if guard is None else [Depends(guard)]
        self.include_router(router, prefix=prefix, dependencies=dependencies)

    @override
    def openapi(self) -> dict[str, Any]:
        if self.openapi_schema is None:
            self.openapi_schema = describe(super().openapi(), self.accesses)
        return self.openapi_schema


def json_block(value: object) -> str:
    return f"<pre>{html.escape(json.dumps(value, indent=2, ensure_ascii=False))}</pre>"


def docs_page(schema: dict[str, Any]) -> str:
    """The page of the document: every operation, its access, its body and its answers, then
    the schemas; plain HTML, no script nor style (the policy of the API loads nothing)."""
    info = schema["info"]
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{html.escape(info['title'])} API {html.escape(info['version'])}</title>",
        '<meta name="robots" content="noindex"></head><body>',
        f"<h1>{html.escape(info['title'])} API {html.escape(info['version'])}</h1>",
        f"<p>{html.escape(info['description'])}</p>",
        '<p><a href="v1/openapi.json">OpenAPI document (JSON)</a></p>',
        "<h2>Authentication</h2>",
    ]
    for name, scheme in schema["components"]["securitySchemes"].items():
        parts.append(f"<p><b>{html.escape(name)}</b>: {html.escape(scheme['description'])}</p>")
    parts.append("<h2>Operations</h2>")
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            title = f"{method.upper()} {path}"
            parts.append(
                f'<h3 id="{html.escape(operation["operationId"])}">{html.escape(title)}</h3>'
            )
            parts.append(f"<p>Access: <b>{html.escape(operation['x-access'])}</b></p>")
            if "description" in operation:
                parts.append(f"<p>{html.escape(operation['description'])}</p>")
            if "parameters" in operation:
                parts.append("<details><summary>Parameters</summary>")
                parts.append(json_block(operation["parameters"]) + "</details>")
            if "requestBody" in operation:
                parts.append("<details><summary>Request body</summary>")
                parts.append(json_block(operation["requestBody"]) + "</details>")
            parts.append("<details><summary>Responses</summary>")
            parts.append(json_block(operation["responses"]) + "</details>")
    parts.append("<h2>Schemas</h2>")
    for name, body in schema["components"]["schemas"].items():
        parts.append(f'<details id="{html.escape(name)}"><summary>{html.escape(name)}</summary>')
        parts.append(json_block(body) + "</details>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"
