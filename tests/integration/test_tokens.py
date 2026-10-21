"""The access tokens through the real API (plan section 3 quater): created by the session of an
administrator and shown once, kept as a fingerprint, read or read and download, never on the
settings nor the tokens, counted (60 a minute), revoked at once, audited."""

import httpx
import pytest

from tests.integration.support import Stack, bearer, new_access_token

pytestmark = [pytest.mark.access, pytest.mark.access_tokens]


def test_a_token_is_shown_once_and_reads_the_api(stack: Stack, client: httpx.Client) -> None:
    created = new_access_token(client, "read", "Grafana")
    secret = created["secret"]

    listed = client.get("/api/v1/tokens").json()["tokens"]
    read = httpx.get(f"{stack.base_url}/api/v1/downloads", headers=bearer(secret), timeout=30.0)

    assert secret.startswith("sd_")
    mine = next(t for t in listed if t["id"] == created["token"]["id"])
    assert mine["name"] == "Grafana"
    assert mine["scope"] == "read"
    assert mine["expires_at"] == mine["created_at"] + 30 * 86400
    assert secret not in str(listed)
    assert read.status_code == 200, read.text
    again = client.get("/api/v1/tokens").json()["tokens"]
    assert next(t for t in again if t["id"] == mine["id"])["last_used_at"] is not None
    database = stack.exec_api("sh", "-c", 'grep -r -l -a -- "$0" /data/shelfdrop || true', secret)
    assert database.stdout.strip() == ""
    assert secret not in stack.api_logs()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/settings"),
        ("GET", "/api/v1/settings/audit"),
        ("GET", "/api/v1/trackers"),
        ("GET", "/api/v1/filters"),
        ("GET", "/api/v1/tokens"),
        ("POST", "/api/v1/tokens"),
        ("GET", "/api/v1/session"),
    ],
)
def test_a_token_never_reaches_the_settings_nor_the_tokens(
    stack: Stack, client: httpx.Client, method: str, path: str
) -> None:
    secret = new_access_token(client, "write")["secret"]

    response = httpx.request(
        method,
        f"{stack.base_url}{path}",
        headers=bearer(secret),
        json={"name": "x", "scope": "write", "days": None},
        timeout=30.0,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "token_forbidden"


def test_a_token_of_reading_never_writes_and_one_of_download_needs_no_origin(
    stack: Stack, client: httpx.Client
) -> None:
    reader = new_access_token(client, "read")["secret"]
    writer = new_access_token(client, "write")["secret"]
    url = f"{stack.base_url}/api/v1/downloads/999999/retry"

    refused = httpx.post(url, headers=bearer(reader), timeout=30.0)
    allowed = httpx.post(url, headers=bearer(writer), timeout=30.0)

    assert refused.status_code == 403
    assert refused.json()["code"] == "token_forbidden"
    # Past the token and the origin: the download itself is unknown.
    assert allowed.status_code == 404
    assert allowed.json()["code"] == "download_not_found"


def test_a_token_revoked_is_refused_at_once_and_audited(stack: Stack, client: httpx.Client) -> None:
    created = new_access_token(client, "write")
    token_id = created["token"]["id"]
    url = f"{stack.base_url}/api/v1/downloads"
    assert httpx.get(url, headers=bearer(created["secret"]), timeout=30.0).status_code == 200

    revoked = client.delete(f"/api/v1/tokens/{token_id}")
    after = httpx.get(url, headers=bearer(created["secret"]), timeout=30.0)
    twice = client.delete(f"/api/v1/tokens/{token_id}")

    assert revoked.status_code == 204
    assert after.status_code == 401
    assert after.json()["code"] == "not_signed_in"
    assert twice.status_code == 404
    assert twice.json()["code"] == "token_not_found"
    assert token_id not in [t["id"] for t in client.get("/api/v1/tokens").json()["tokens"]]
    audit = client.get("/api/v1/settings/audit").json()["entries"]
    mine = [(e["action"], e["actor"]) for e in audit if e["target"] == f"token.{token_id}"]
    assert mine == [("revoked", "admin"), ("created", "admin")]
    assert created["secret"] not in str(audit)


@pytest.mark.parametrize("header", [None, "Bearer sd_made-up", "Basic dXNlcjpwYXNz"])
def test_without_a_valid_token_the_api_answers_401(stack: Stack, header: str | None) -> None:
    headers = {} if header is None else {"Authorization": header}

    response = httpx.get(f"{stack.base_url}/api/v1/downloads", headers=headers, timeout=30.0)

    assert response.status_code == 401
    assert response.json()["code"] == "not_signed_in"


def test_a_token_makes_60_requests_a_minute(stack: Stack, client: httpx.Client) -> None:
    secret = new_access_token(client, "read")["secret"]
    url = f"{stack.base_url}/api/v1/downloads"

    with httpx.Client(headers=bearer(secret), timeout=30.0) as http:
        statuses = [http.get(url).status_code for _ in range(61)]
    other = new_access_token(client, "read")["secret"]

    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429
    assert httpx.get(url, headers=bearer(other), timeout=30.0).status_code == 200
