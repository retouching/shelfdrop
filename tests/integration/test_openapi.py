"""The OpenAPI document through the real API (plan section 3 quater): served to the session of an
administrator alone, the same as docs/openapi.json, with the access of each operation, and its
page without a script."""

import json
from pathlib import Path

import httpx
import pytest

from tests.integration.support import Stack, bearer, new_access_token

pytestmark = [pytest.mark.access, pytest.mark.access_openapi]

COMMITTED = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def test_the_document_served_is_the_one_of_the_repository(client: httpx.Client) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    served = response.json()
    assert served == json.loads(COMMITTED.read_text(encoding="utf-8"))
    token = served["components"]["securitySchemes"]["token"]
    assert (token["type"], token["scheme"]) == ("http", "bearer")
    assert served["paths"]["/api/v1/downloads"]["post"]["x-access"] == "write"
    assert served["paths"]["/api/v1/settings"]["get"]["x-access"] == "session"


def test_every_route_of_the_document_answers_as_it_says(stack: Stack, client: httpx.Client) -> None:
    """Each operation `read` of the document lets a token of reading in (whatever it answers
    then), each `session` one refuses it, each `write` one refuses it for a write."""
    document = client.get("/api/v1/openapi.json").json()
    secret = new_access_token(client, "read")["secret"]
    statuses: dict[str, set[int]] = {"session": set(), "write": set(), "read": set()}

    with httpx.Client(base_url=stack.base_url, headers=bearer(secret), timeout=30.0) as http:
        for path, operations in document["paths"].items():
            if "{" in path or not path.startswith("/api/"):
                continue
            for method, operation in operations.items():
                access = operation["x-access"]
                if access == "public" or (access == "read" and method != "get"):
                    continue
                statuses[access].add(http.request(method.upper(), path, json={}).status_code)

    assert statuses["session"] == {403}
    assert statuses["write"] == {403}
    assert statuses["read"]
    assert not statuses["read"] & {401, 403}


def test_the_page_lists_the_operations_for_the_session_alone(
    stack: Stack, client: httpx.Client, anonymous: httpx.Client
) -> None:
    secret = new_access_token(client, "write")["secret"]

    page = client.get("/api/docs")
    with_token = httpx.get(f"{stack.base_url}/api/docs", headers=bearer(secret), timeout=30.0)
    without = anonymous.get("/api/docs")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert page.headers["content-security-policy"].startswith("default-src 'none'")
    assert "POST /api/v1/downloads" in page.text
    assert "<script" not in page.text
    assert with_token.status_code == 403
    assert with_token.json()["code"] == "token_forbidden"
    assert without.status_code == 401
