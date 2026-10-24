"""Integration fixtures: one throwaway Compose stack per pytest session."""

import secrets
from collections.abc import Iterator

import httpx
import pytest

from tests.integration.support import (
    FAKE_ORIGIN,
    JELLYFIN_API_KEY,
    QUI_KEY,
    UP_TIMEOUT_SECONDS,
    WEBHOOK,
    FakeSources,
    Stack,
    compose,
    cookie_of,
    discord_stub,
    jellyfin_stubs,
    prowlarr_stubs,
    qbittorrent_stubs,
    recorded_stubs,
    sign_in,
    signed_in_headers,
)


@pytest.fixture(scope="session")
def stack() -> Iterator[Stack]:
    project = f"shelfdrop-test-{secrets.token_hex(4)}"
    try:
        up = compose(
            project,
            "up",
            "--detach",
            "--build",
            "--wait",
            "--wait-timeout",
            "180",
            timeout=UP_TIMEOUT_SECONDS,
        )
        if up.returncode != 0:
            logs = compose(project, "logs", "--no-color")
            pytest.fail(
                f"`docker compose up` failed for {project}:\n{up.stderr}\n"
                f"--- logs ---\n{logs.stdout}{logs.stderr}",
                pytrace=False,
            )
        built = Stack(project=project)
        try:
            built.read_ports()
        except RuntimeError as error:
            pytest.fail(str(error), pytrace=False)
        FakeSources(built.sources_url).load(
            [
                *recorded_stubs(),
                *prowlarr_stubs(),
                *jellyfin_stubs(),
                *qbittorrent_stubs(),
                discord_stub(),
            ]
        )
        yield built
    finally:
        compose(project, "down", "--volumes", "--remove-orphans")


@pytest.fixture
def fake_sources(stack: Stack) -> FakeSources:
    return FakeSources(stack.sources_url)


@pytest.fixture(scope="session")
def session_token(stack: Stack) -> str:
    """One session of the administrator for the whole run: the sign-ins are counted (5 a
    minute from one address), the tests of the sign-in make their own."""
    response = sign_in(stack.base_url)
    assert response.status_code == 200, response.text
    return cookie_of(response)


@pytest.fixture
def signed_in(stack: Stack, session_token: str) -> dict[str, str]:
    """The headers of a request of the pages, signed in, for the port of now."""
    return signed_in_headers(stack.base_url, session_token)


@pytest.fixture
def client(stack: Stack, signed_in: dict[str, str]) -> Iterator[httpx.Client]:
    """A client of the pages, signed in as the administrator."""
    with httpx.Client(base_url=stack.base_url, timeout=30.0, headers=signed_in) as http_client:
        yield http_client


@pytest.fixture
def anonymous(stack: Stack) -> Iterator[httpx.Client]:
    """A client without a session, from the pages (its Origin)."""
    headers = {"Origin": stack.base_url}
    with httpx.Client(base_url=stack.base_url, timeout=30.0, headers=headers) as http_client:
        yield http_client


@pytest.fixture
def qbittorrent_saved(client: httpx.Client) -> Iterator[None]:
    """qBittorrent saved in the settings (the fake one, behind qui), then cleared again."""
    saved = {
        "values": {"torrent.url": FAKE_ORIGIN},
        "secrets": {"torrent.api_key": QUI_KEY},
    }
    client.put("/api/v1/settings", json=saved).raise_for_status()
    yield
    cleared = {"values": {"torrent.url": None}, "secrets": {"torrent.api_key": None}}
    client.put("/api/v1/settings", json=cleared).raise_for_status()


@pytest.fixture
def webhook_saved(client: httpx.Client) -> Iterator[None]:
    """The webhook of the journal saved (the fake one), then cleared again."""
    client.put(
        "/api/v1/settings", json={"secrets": {"discord.webhook": WEBHOOK}}
    ).raise_for_status()
    yield
    client.put("/api/v1/settings", json={"secrets": {"discord.webhook": None}}).raise_for_status()


@pytest.fixture(scope="session")
def media(stack: Stack) -> None:
    """The torrents, the libraries and the folder of the uploads of the tests, in the volume of
    the placement worker:
    owned by its user and the group of the library, group-writable."""
    folders = (
        "/data/torrents /data/files/comics /data/files/ebooks /data/files/audiobooks /data/envois"
    )
    stack.exec_placement(
        "sh",
        "-c",
        f"mkdir -p {folders} && chown -R 10001:1000 /data/torrents /data/files /data/envois"
        " && chmod -R 2775 /data/torrents /data/files /data/envois",
        root=True,
    )


@pytest.fixture
def jellyfin_saved(client: httpx.Client) -> Iterator[None]:
    """The API key of the fake Jellyfin saved (its address comes from the environment)."""
    saved = {"secrets": {"jellyfin.api_key": JELLYFIN_API_KEY}}
    client.put("/api/v1/settings", json=saved).raise_for_status()
    yield
    client.put("/api/v1/settings", json={"secrets": {"jellyfin.api_key": None}}).raise_for_status()
