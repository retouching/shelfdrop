"""shelfdrop.http.openapi: the document of the API, who may call each operation, its page."""

from pathlib import Path
from typing import Any

import pytest

from shelfdrop.http.openapi import docs_page
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
    codes = schema["components"]["schemas"]["ErrorResponse"]["$defs"]["ErrorCode"]["enum"]
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


def test_the_page_lists_every_operation_without_a_script(schema: dict[str, Any]) -> None:
    page = docs_page(schema)

    assert '<h3 id="send_downloads_api_v1_downloads_post">POST /api/v1/downloads</h3>' in page
    assert "Access: <b>write</b>" in page
    assert "<script" not in page
    assert "<style" not in page
    assert page.count("<h3 ") == sum(len(ops) for ops in schema["paths"].values())
