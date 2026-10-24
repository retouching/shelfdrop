"""The OpenAPI documents of the API (ADR 0021): the schema FastAPI builds from the routes, with who
may call each operation (the session, an access token and its scope) and the error body of every
refusal; and the public one, the operations an access token reaches alone, which `/api/docs`
shows. `python -m shelfdrop.openapi` writes both to docs/.
"""

import copy
from collections.abc import Callable, Iterator
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
    '`{"code", "detail", "data"}`; the codes are listed in the schema `ErrorCode`.'
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
SCHEMA_PREFIX: Final = "#/components/schemas/"
PUBLIC_ACCESSES: Final[frozenset[Access]] = frozenset({"read", "write"})
PUBLIC_DESCRIPTION: Final = (
    "The API of shelfdrop for a program: the work search, the releases of Prowlarr, the "
    "downloads, Ranger, the waiting searches. Every request sends an access token created on "
    "the page Paramètres, API et MCP: `Authorization: Bearer sd_...`. Each operation names the "
    "scope it needs in `x-access`: `read` (any token) or `write` (a token `write`). Every error "
    'body is `{"code", "detail", "data"}`; the codes are listed in the schema `ErrorCode`.'
)
PUBLIC_REFUSALS: Final[dict[Access, dict[str, str]]] = {
    "read": {
        "401": "No token, or a token unknown, expired or revoked (`not_signed_in`).",
        "429": "More than 60 requests in a minute with this token (`too_many_requests`).",
    },
    "write": {
        "401": "No token, or a token unknown, expired or revoked (`not_signed_in`).",
        "403": "A token of reading (`token_forbidden`).",
        "429": "More than 60 requests in a minute with this token (`too_many_requests`).",
    },
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
    error = ErrorResponse.model_json_schema(ref_template=SCHEMA_PREFIX + "{model}")
    # Its enums go beside it, where its references point.
    schemas.update(error.pop("$defs", {}))
    schemas["ErrorResponse"] = error
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


def references(value: object) -> Iterator[str]:
    """The names of the schemas `value` points to, at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str) and item.startswith(SCHEMA_PREFIX):
                yield item.removeprefix(SCHEMA_PREFIX)
            else:
                yield from references(item)
    elif isinstance(value, list):
        for item in value:
            yield from references(item)


def public_document(schema: dict[str, Any]) -> dict[str, Any]:
    """The document of the operations an access token reaches (`read`, `write`): nothing of the
    session nor of the public routes, the schemas they use alone, the token as the only security
    scheme. `schema` is the document of `describe`, left as it is."""
    public = copy.deepcopy(schema)
    public["info"]["description"] = PUBLIC_DESCRIPTION
    paths: dict[str, Any] = {}
    for path, operations in public["paths"].items():
        kept = {m: o for m, o in operations.items() if o["x-access"] in PUBLIC_ACCESSES}
        for operation in kept.values():
            operation["security"] = [{"token": []}]
            access = operation["x-access"]
            for status, text in PUBLIC_REFUSALS[access].items():
                response = operation["responses"][status]
                if response["description"] == REFUSALS[access][status]:
                    response["description"] = text
        if kept:
            paths[path] = kept
    public["paths"] = paths
    schemas = public["components"]["schemas"]
    used: set[str] = set()
    pending = list(references(paths))
    while pending:
        name = pending.pop()
        if name not in used:
            used.add(name)
            pending.extend(references(schemas[name]))
    public["components"] = {
        "schemas": {name: body for name, body in schemas.items() if name in used},
        "securitySchemes": {"token": SECURITY_SCHEMES["token"]},
    }
    return public


class DocumentedApi(FastAPI):
    """The application, whose `openapi()` is the document of ADR 0021, written to
    docs/openapi.json, and `public_openapi()` its part for the access tokens, served at
    `/api/v1/openapi.json` and shown by `/api/docs`. Its routers come through `include`, which
    keeps who may call each operation."""

    def __init__(self, **options: Any) -> None:
        super().__init__(**options)
        self.accesses: dict[tuple[str, str], Access] = {}
        self.public_schema: dict[str, Any] | None = None

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

    def public_openapi(self) -> dict[str, Any]:
        if self.public_schema is None:
            self.public_schema = public_document(self.openapi())
        return self.public_schema
