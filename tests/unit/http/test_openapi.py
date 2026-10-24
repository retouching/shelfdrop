"""shelfdrop.http.openapi: the document of the API, who may call each operation, and its public
part for the access tokens."""

from pathlib import Path
from typing import Any

import pytest

from shelfdrop.http.openapi import public_document
from shelfdrop.main import build_app
from tests.unit.test_main import settings_for


@pytest.fixture
def schema(tmp_path: Path) -> dict[str, Any]:
    return build_app(settings_for(tmp_path)).openapi()


@pytest.mark.parametrize(
    ("method", "path", "access"),
    [
        ("get", "/health", "public"),
        ("post", "/api/v1/session", "public"),
        ("get", "/api/v1/session", "session"),
        ("get", "/api/v1/settings", "session"),
        ("put", "/api/v1/filters", "session"),
        ("post", "/api/v1/tokens", "session"),
        ("post", "/api/v1/searches", "read"),
        ("get", "/api/v1/releases/{release_id}/torrent", "read"),
        ("get", "/api/v1/works", "read"),
        ("get", "/api/v1/downloads", "read"),
        ("post", "/api/v1/downloads", "write"),
        ("post", "/api/v1/downloads/{download_id}/retry", "write"),
        ("post", "/api/v1/place/items/{item_id}/link", "write"),
        ("post", "/api/v1/waiting", "write"),
    ],
)
def test_each_operation_names_who_may_call_it(
    schema: dict[str, Any], method: str, path: str, access: str
) -> None:
    operation = schema["paths"][path][method]

    assert operation["x-access"] == access
    names = [next(iter(r)) for r in operation["security"]]
    expected = {"public": [], "session": ["session"]}.get(access, ["session", "token"])
    assert names == expected


def test_the_refusals_and_the_errors_are_the_error_body(schema: dict[str, Any]) -> None:
    send = schema["paths"]["/api/v1/downloads"]["post"]["responses"]
    settings = schema["paths"]["/api/v1/settings"]["get"]["responses"]
    ref = {"$ref": "#/components/schemas/ErrorResponse"}

    for status in ("401", "403", "422", "429"):
        assert send[status]["content"]["application/json"]["schema"] == ref
    assert "429" not in settings
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    codes = schema["components"]["schemas"]["ErrorCode"]["enum"]
    assert {"token_forbidden", "too_many_requests", "not_signed_in"} <= set(codes)


def test_the_token_is_a_bearer_and_the_session_its_cookie(schema: dict[str, Any]) -> None:
    schemes = schema["components"]["securitySchemes"]

    assert schemes["token"]["scheme"] == "bearer"
    assert (schemes["session"]["in"], schemes["session"]["name"]) == ("cookie", "__Host-shelfdrop")


def test_the_bodies_of_the_program_carry_examples(schema: dict[str, Any]) -> None:
    schemas = schema["components"]["schemas"]

    for name in ("SearchCreate", "DownloadsCreate", "WaitingCreate", "TokenCreate"):
        assert schemas[name]["examples"], name


def test_the_document_and_its_page_are_not_in_the_document(schema: dict[str, Any]) -> None:
    assert "/api/docs" not in schema["paths"]
    assert "/api/v1/openapi.json" not in schema["paths"]


def test_every_reference_names_a_schema_of_the_document(schema: dict[str, Any]) -> None:
    names = set(schema["components"]["schemas"])

    assert set(references(schema)) <= names
    assert "$defs" not in schema["components"]["schemas"]["ErrorResponse"]


def references(value: object) -> list[str]:
    if isinstance(value, dict):
        found = [] if "$ref" not in value else [str(value["$ref"]).rsplit("/", 1)[-1]]
        return found + [r for item in value.values() for r in references(item)]
    if isinstance(value, list):
        return [r for item in value for r in references(item)]
    return []


def test_the_public_document_holds_the_operations_of_the_tokens_alone(
    schema: dict[str, Any],
) -> None:
    public = public_document(schema)

    accesses = {op["x-access"] for ops in public["paths"].values() for op in ops.values()}
    expected = sum(
        1
        for ops in schema["paths"].values()
        for op in ops.values()
        if op["x-access"] in ("read", "write")
    )
    assert accesses == {"read", "write"}
    assert sum(len(ops) for ops in public["paths"].values()) == expected
    for path in ("/health", "/api/v1/session", "/api/v1/settings", "/api/v1/tokens"):
        assert path not in public["paths"]
    assert "post" in public["paths"]["/api/v1/downloads"]
    assert "session" not in public["info"]["description"]


def test_the_public_document_names_the_token_alone(schema: dict[str, Any]) -> None:
    public = public_document(schema)

    assert list(public["components"]["securitySchemes"]) == ["token"]
    send = public["paths"]["/api/v1/downloads"]["post"]
    assert send["security"] == [{"token": []}]
    for status in ("401", "403", "429"):
        assert "session" not in send["responses"][status]["description"].lower()
        assert "origin" not in send["responses"][status]["description"].lower()


def test_the_public_document_keeps_the_schemas_it_uses_alone(schema: dict[str, Any]) -> None:
    public = public_document(schema)

    schemas = set(public["components"]["schemas"])
    assert set(references(public)) == schemas
    assert {"ErrorResponse", "ErrorCode", "DownloadsCreate", "SearchCreate"} <= schemas
    assert not {"TokenCreate", "SettingsUpdate"} & schemas


def test_the_public_document_leaves_the_document_as_it_is(schema: dict[str, Any]) -> None:
    public_document(schema)

    assert "/api/v1/settings" in schema["paths"]
    assert "session" in schema["components"]["securitySchemes"]
