"""The OpenAPI documents through the real API (ADR 0021): the public one served to a session or
any token, the same as docs/openapi.public.json; every operation of docs/openapi.json answering as
its access says; the page of Swagger UI, its script and its style from the same origin alone."""

import json
import re
from pathlib import Path

import httpx
import pytest

from tests.integration.support import Stack, bearer, new_access_token

pytestmark = [pytest.mark.access, pytest.mark.access_openapi]

DOCS = Path(__file__).resolve().parents[2] / "docs"
COMMITTED = DOCS / "openapi.json"
PUBLIC = DOCS / "openapi.public.json"


def test_the_document_served_is_the_public_one_of_the_repository(
    stack: Stack, client: httpx.Client, anonymous: httpx.Client
) -> None:
    secret = new_access_token(client, "read")["secret"]

    response = client.get("/api/v1/openapi.json")
    with_token = httpx.get(
        f"{stack.base_url}/api/v1/openapi.json", headers=bearer(secret), timeout=30.0
    )
    without = anonymous.get("/api/v1/openapi.json")

    assert response.status_code == 200
    served = response.json()
    assert served == json.loads(PUBLIC.read_text(encoding="utf-8"))
    assert with_token.status_code == 200
    assert with_token.json() == served
    assert without.status_code == 401
    assert list(served["components"]["securitySchemes"]) == ["token"]
    assert served["paths"]["/api/v1/downloads"]["post"]["x-access"] == "write"
    assert "/api/v1/settings" not in served["paths"]
    accesses = {op["x-access"] for ops in served["paths"].values() for op in ops.values()}
    assert accesses == {"read", "write"}


def test_every_route_of_the_document_answers_as_it_says(stack: Stack, client: httpx.Client) -> None:
    """Each operation `read` of the whole document (docs/openapi.json, every route) lets a token
    of reading in (whatever it answers then), each `session` one refuses it, each `write` one
    refuses it for a write."""
    document = json.loads(COMMITTED.read_text(encoding="utf-8"))
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


def test_the_page_is_swagger_ui_from_the_same_origin(
    stack: Stack, client: httpx.Client, anonymous: httpx.Client
) -> None:
    secret = new_access_token(client, "read")["secret"]

    page = client.get("/api/docs")
    with_token = httpx.get(f"{stack.base_url}/api/docs", headers=bearer(secret), timeout=30.0)
    without = anonymous.get("/api/docs")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    policy = page.headers["content-security-policy"]
    assert policy.startswith("default-src 'none'")
    assert "script-src 'self'" in policy
    assert "style-src 'self'" in policy
    assert "unsafe" not in policy
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", page.text, flags=re.DOTALL)
    assert scripts
    assert all(body == "" and 'src="/assets/' in attributes for attributes, body in scripts)
    assert "<style" not in page.text
    assert with_token.status_code == 200
    assert with_token.text == page.text
    assert without.status_code == 401


def test_the_script_and_the_style_of_the_page_are_served(client: httpx.Client) -> None:
    page = client.get("/api/docs").text
    script = re.findall(r'<script[^>]* src="([^"]+)"', page)[0]
    style = re.findall(r'<link rel="stylesheet"[^>]* href="([^"]+)"', page)[0]

    loaded = client.get(script)
    styled = client.get(style)

    assert loaded.status_code == 200
    assert "javascript" in loaded.headers["content-type"]
    assert "swagger-ui" in loaded.text
    assert styled.status_code == 200
    assert "text/css" in styled.headers["content-type"]
    assert ".swagger-ui" in styled.text
