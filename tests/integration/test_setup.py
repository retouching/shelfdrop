"""The set-up of the first launch through the real API (ADR 0023), on an API of its own: the
service `api-setup` of docker/compose.test.yaml, on an empty database and without the settings
of the environment, against the fake Prowlarr, qBittorrent (behind qui) and Jellyfin. Its sign-ins
are counted by its own process. And, on the stack shared, the internal account created from the
settings of an installation signed in through Jellyfin."""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from tests.integration.support import (
    FAKE_ORIGIN,
    JELLYFIN_API_KEY,
    PROWLARR_KEY,
    QUI_KEY,
    UP_TIMEOUT_SECONDS,
    Stack,
    compose,
    cookie_of,
    published,
    signed_in_headers,
)

pytestmark = [pytest.mark.auth, pytest.mark.auth_setup]

SERVICE = "api-setup"
OWNER = ("owner", "owner-password-of-the-tests")
NEW_PASSWORD = "owner-new-password-of-the-tests"
# The internal account of the stack shared: another name than the accounts of the fake
# Jellyfin, which keep signing in there.
KEEPER = ("keeper", "keeper-password-of-the-tests")


@pytest.fixture(scope="module")
def fresh(stack: Stack) -> Iterator[str]:
    """The address of an API started on an empty database, without Prowlarr nor Jellyfin in
    its environment; removed at the end of the module."""
    up = compose(
        stack.project,
        "--profile",
        "setup",
        "up",
        "--detach",
        "--wait",
        "--wait-timeout",
        "180",
        SERVICE,
        timeout=UP_TIMEOUT_SECONDS,
    )
    try:
        assert up.returncode == 0, up.stderr
        yield published(stack.project, SERVICE, "8000")
    finally:
        compose(stack.project, "--profile", "setup", "rm", "--stop", "--force", SERVICE)


def logs_of(stack: Stack) -> str:
    result = compose(stack.project, "logs", "--no-color", "--no-log-prefix", SERVICE)
    return result.stdout + result.stderr


def pages(base_url: str, token: str | None = None) -> httpx.Client:
    """A client of the pages of `base_url` (its Origin), signed in with `token`."""
    headers = {"Origin": base_url} if token is None else signed_in_headers(base_url, token)
    return httpx.Client(base_url=base_url, timeout=30.0, headers=headers)


def sign_in(base_url: str, username: str, password: str) -> httpx.Response:
    with pages(base_url) as client:
        return client.post("/api/v1/session", json={"username": username, "password": password})


def probe(client: httpx.Client, service: str) -> dict[str, Any]:
    response = client.post("/api/v1/settings/test", json={"service": service})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_the_first_launch_goes_through_the_set_up_and_its_account_signs_in(
    stack: Stack, fresh: str
) -> None:
    with pages(fresh) as anonymous:
        assert anonymous.get("/api/v1/setup").json() == {"needed": True, "account": False}
        closed = anonymous.get("/api/v1/downloads")
        assert (closed.status_code, closed.json()["code"]) == (409, "setup_required")
        assert anonymous.get("/health").status_code == 200
        assert anonymous.get("/").status_code == 200
        assert anonymous.post("/api/v1/setup/finish").status_code == 401
        created = anonymous.post(
            "/api/v1/setup/account", json={"username": OWNER[0], "password": OWNER[1]}
        )
        assert created.status_code == 200, created.text
        assert created.json() == {"username": OWNER[0], "internal": True}
        second = anonymous.post(
            "/api/v1/setup/account", json={"username": "other", "password": OWNER[1]}
        )
        assert (second.status_code, second.json()["code"]) == (409, "account_exists")
    token = cookie_of(created)

    with pages(fresh, token) as client:
        assert client.get("/api/v1/setup").json() == {"needed": True, "account": True}
        assert client.get("/api/v1/downloads").status_code == 409
        # Prowlarr, then qBittorrent behind qui: saved, then tested with what is saved.
        client.put(
            "/api/v1/settings",
            json={
                "values": {"prowlarr.url": FAKE_ORIGIN},
                "secrets": {"prowlarr.api_key": PROWLARR_KEY},
            },
        ).raise_for_status()
        assert probe(client, "prowlarr")["ok"] is True
        client.put(
            "/api/v1/settings",
            json={
                "values": {"qbittorrent.url": FAKE_ORIGIN},
                "secrets": {"qbittorrent.api_key": QUI_KEY},
            },
        ).raise_for_status()
        assert probe(client, "qbittorrent")["ok"] is True
        # Jellyfin is required: the set-up does not end without it.
        early = client.post("/api/v1/setup/finish")
        assert (early.status_code, early.json()["code"]) == (409, "jellyfin_not_connected")
        client.put(
            "/api/v1/settings",
            json={
                "values": {"jellyfin.url": FAKE_ORIGIN},
                "secrets": {"jellyfin.api_key": JELLYFIN_API_KEY},
            },
        ).raise_for_status()
        assert probe(client, "jellyfin")["ok"] is True
        # The libraries and the folder of the uploads.
        folders = {
            "placement.library.manga": "/data/files/comics",
            "placement.library.ebook": "/data/files/ebooks",
            "placement.library.audiobook": "/data/files/audiobooks",
            "uploads.folder": "/data/envois",
        }
        saved = client.put("/api/v1/settings", json={"values": folders})
        assert saved.status_code == 200, saved.text

        finished = client.post("/api/v1/setup/finish")

        assert finished.status_code == 200, finished.text
        assert finished.json() == {"needed": False, "account": True}
        assert client.get("/api/v1/downloads").status_code == 200
        again = client.post(
            "/api/v1/setup/account", json={"username": "other", "password": OWNER[1]}
        )
        assert (again.status_code, again.json()["code"]) == (409, "setup_done")
        assert client.delete("/api/v1/session").status_code == 204

    # The internal account signs in again (its name in any case); two sessions, and a new
    # password ends the other one.
    first = sign_in(fresh, OWNER[0].upper(), OWNER[1])
    assert first.status_code == 200, first.text
    assert first.json() == {"username": OWNER[0], "internal": True}
    kept = cookie_of(first)
    other = cookie_of(sign_in(fresh, *OWNER))

    with pages(fresh, kept) as client:
        assert client.get("/api/v1/account").json()["account"]["username"] == OWNER[0]
        wrong = client.put(
            "/api/v1/account/password", json={"current": "not-it", "new": NEW_PASSWORD}
        )
        assert (wrong.status_code, wrong.json()["code"]) == (422, "password_refused")
        changed = client.put(
            "/api/v1/account/password", json={"current": OWNER[1], "new": NEW_PASSWORD}
        )
        assert changed.status_code == 200, changed.text
        assert client.get("/api/v1/session").status_code == 200
    with pages(fresh, other) as client:
        assert client.get("/api/v1/session").status_code == 401
    logs = logs_of(stack)
    assert OWNER[1] not in logs
    assert NEW_PASSWORD not in logs


def test_an_account_created_from_the_settings_leaves_the_site_open(
    client: httpx.Client, anonymous: httpx.Client
) -> None:
    """The stack shared, signed in through Jellyfin: no set-up, an internal account created
    from the settings, never a second one."""
    assert anonymous.get("/api/v1/setup").json()["needed"] is False
    created = client.post("/api/v1/account", json={"username": KEEPER[0], "password": KEEPER[1]})
    # Created here, or by an earlier test of the same stack.
    assert created.status_code in (201, 409), created.text
    second = client.post("/api/v1/account", json={"username": "other", "password": KEEPER[1]})

    assert (second.status_code, second.json()["code"]) == (409, "account_exists")
    assert client.get("/api/v1/account").json()["account"]["username"] == KEEPER[0]
    assert anonymous.get("/api/v1/setup").json() == {"needed": False, "account": True}
    assert client.get("/api/v1/downloads").status_code == 200
