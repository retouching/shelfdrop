"""The headers of the real API and of its pages."""

import httpx
import pytest

pytestmark = [pytest.mark.security, pytest.mark.security_headers]

COMMON = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


@pytest.mark.parametrize("path", ["/health", "/api/v1/works?q=a", "/api/v1/nothing"])
def test_an_api_answer_is_never_cached_and_loads_nothing(client: httpx.Client, path: str) -> None:
    response = client.get(path)

    for name, value in COMMON.items():
        assert response.headers[name] == value
    assert response.headers["cache-control"] == "no-store"
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )


def test_a_page_loads_from_its_own_origin(client: httpx.Client) -> None:
    response = client.get("/")

    for name, value in COMMON.items():
        assert response.headers[name] == value
    policy = response.headers["content-security-policy"]
    assert policy.startswith("default-src 'self'")
    assert "frame-ancestors 'none'" in policy
    assert response.headers.get("cache-control") == "no-cache"


@pytest.mark.parametrize("path", ["/health", "/", "/api/v1/nothing"])
def test_no_server_header(client: httpx.Client, path: str) -> None:
    assert "server" not in client.get(path).headers


def test_a_valid_request_id_comes_back(client: httpx.Client) -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc.DEF_123-x"})

    assert response.headers["x-request-id"] == "abc.DEF_123-x"


@pytest.mark.parametrize("sent", ["", "with space", "x" * 129, "semi;colon"])
def test_an_invalid_request_id_is_replaced(client: httpx.Client, sent: str) -> None:
    response = client.get("/health", headers={"X-Request-ID": sent})

    returned = response.headers["x-request-id"]
    assert returned != sent
    assert len(returned) == 32
