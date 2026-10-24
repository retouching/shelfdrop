"""The sign-in through the real API: administrators of Jellyfin alone, a
refusal that never says what is wrong, credentials never logged, and the attempts counted.
Last of the part `auth`: its last test uses up the attempts of the minute."""

import httpx
import pytest

from tests.integration.support import (
    ADMIN,
    READER,
    FakeSources,
    Stack,
    cookie_of,
    new_request_id,
    signed_in_headers,
)

pytestmark = [pytest.mark.auth, pytest.mark.auth_sign_in]


def post_sign_in(stack: Stack, username: str, password: str, request_id: str) -> httpx.Response:
    return httpx.post(
        f"{stack.base_url}/api/v1/session",
        json={"username": username, "password": password},
        headers={"Origin": stack.base_url, "X-Request-ID": request_id},
        timeout=30.0,
    )


def authentications(fake_sources: FakeSources) -> int:
    response = httpx.post(
        f"{fake_sources.url}/__admin/requests/count",
        json={"method": "POST", "urlPath": "/Users/AuthenticateByName"},
        timeout=10.0,
    )
    response.raise_for_status()
    count: int = response.json()["count"]
    return count


def test_an_administrator_signs_in_with_a_strict_cookie(stack: Stack) -> None:
    response = post_sign_in(stack, *ADMIN, new_request_id())

    assert response.status_code == 200
    assert response.json() == {"username": "admin"}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-shelfdrop=")
    for attribute in ("Secure", "HttpOnly", "SameSite=strict", "Path=/", "Max-Age=2592000"):
        assert attribute in cookie
    assert "Domain" not in cookie
    token = cookie_of(response)
    assert len(token) >= 43
    read = httpx.get(
        f"{stack.base_url}/api/v1/session",
        headers=signed_in_headers(stack.base_url, token),
        timeout=30.0,
    )
    assert read.json() == {"username": "admin"}


@pytest.mark.parametrize(
    "account", [READER, (ADMIN[0], "wrong-password-77c1")], ids=["not-admin", "wrong-password"]
)
def test_every_refusal_is_the_same_and_logs_no_credential(
    stack: Stack, account: tuple[str, str]
) -> None:
    request_id = new_request_id()

    response = post_sign_in(stack, *account, request_id)

    assert response.status_code == 401
    assert response.json() == {"code": "login_refused", "detail": "Login refused", "data": None}
    assert "set-cookie" not in response.headers
    records = stack.log_records(request_id, expected=2)
    assert any(record["message"] == "Sign-in refused" for record in records)
    logs = stack.api_logs()
    assert account[1] not in logs
    assert ADMIN[1] not in logs


def test_the_attempts_of_a_minute_are_counted(stack: Stack, fake_sources: FakeSources) -> None:
    """5 attempts a minute from one address: the runs before already made some, so the
    refusal comes within 6 more, and the attempt refused is never sent to Jellyfin."""
    before = authentications(fake_sources)
    statuses: list[int] = []
    for _ in range(6):
        response = post_sign_in(stack, ADMIN[0], "wrong-password-77c1", new_request_id())
        statuses.append(response.status_code)
        if response.status_code == 429:
            break

    assert statuses[-1] == 429
    assert set(statuses[:-1]) <= {401}
    assert authentications(fake_sources) == before + len(statuses) - 1
    refused = post_sign_in(stack, *ADMIN, new_request_id())
    assert refused.json() == {
        "code": "too_many_attempts",
        "detail": "Too many attempts",
        "data": None,
    }
