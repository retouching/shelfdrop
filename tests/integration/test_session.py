"""The sessions through the real API: without one, every route of the API
answers 401 but the sign-in, /health and the pages; a write needs the Origin of the pages; a
sign-out ends the session."""

import httpx
import pytest

from tests.integration.support import Stack, cookie_of, sign_in, signed_in_headers

pytestmark = [pytest.mark.auth, pytest.mark.auth_session]

ROUTES = [
    ("GET", "/api/v1/works?q=Berserk&kind=manga"),
    ("GET", "/api/v1/works/kitsu:1"),
    ("POST", "/api/v1/searches"),
    ("GET", "/api/v1/searches/x"),
    ("GET", "/api/v1/searches/x/events"),
    ("GET", "/api/v1/trackers"),
    ("POST", "/api/v1/trackers/refresh"),
    ("PUT", "/api/v1/trackers"),
    ("GET", "/api/v1/filters"),
    ("PUT", "/api/v1/filters"),
    ("GET", "/api/v1/session"),
    ("DELETE", "/api/v1/session"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_without_a_session_every_route_answers_401(
    anonymous: httpx.Client, method: str, path: str
) -> None:
    response = anonymous.request(method, path, json={})

    assert response.status_code == 401
    assert response.json() == {"code": "not_signed_in", "detail": "Not signed in", "data": None}


def test_a_made_up_cookie_is_no_session(stack: Stack) -> None:
    headers = signed_in_headers(stack.base_url, "made-up-token")

    response = httpx.get(f"{stack.base_url}/api/v1/trackers", headers=headers, timeout=30.0)

    assert response.status_code == 401


def test_the_probe_and_the_pages_need_no_session(anonymous: httpx.Client) -> None:
    assert anonymous.get("/health").status_code == 200
    page = anonymous.get("/parametres")
    assert page.status_code == 200
    assert "<!doctype html>" in page.text.lower()


@pytest.mark.parametrize("origin", [None, "https://evil.example", "null"])
def test_a_write_from_another_origin_is_refused_even_signed_in(
    stack: Stack, signed_in: dict[str, str], origin: str | None
) -> None:
    headers = {"Cookie": signed_in["Cookie"]}
    if origin is not None:
        headers["Origin"] = origin

    response = httpx.put(
        f"{stack.base_url}/api/v1/trackers", json={"trackers": []}, headers=headers, timeout=30.0
    )

    assert response.status_code == 403
    assert response.json()["code"] == "origin_refused"


def test_a_read_with_the_session_needs_no_origin(stack: Stack, signed_in: dict[str, str]) -> None:
    response = httpx.get(
        f"{stack.base_url}/api/v1/session", headers={"Cookie": signed_in["Cookie"]}, timeout=30.0
    )

    assert response.json() == {"username": "admin"}


def test_a_sign_out_ends_the_session(stack: Stack) -> None:
    token = cookie_of(sign_in(stack.base_url))
    headers = signed_in_headers(stack.base_url, token)

    out = httpx.delete(f"{stack.base_url}/api/v1/session", headers=headers, timeout=30.0)
    after = httpx.get(f"{stack.base_url}/api/v1/session", headers=headers, timeout=30.0)

    assert out.status_code == 204
    assert "__Host-shelfdrop=" in out.headers["set-cookie"]
    assert "Max-Age=0" in out.headers["set-cookie"]
    assert after.status_code == 401
