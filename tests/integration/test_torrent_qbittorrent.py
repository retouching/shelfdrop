"""A real qBittorrent (the service `qbittorrent` of the test stack, its profile
`torrent-qbittorrent`) chosen in the settings as `qbittorrent`, signed in with the account of
its WebUI: the test of the connection and the categories it misses, then a release sent through
the real API, listed with its generic status, its category and its path, and marked placed.

qBittorrent finds no peer there: a torrent added stays stalled (`stalledDL`, F63)."""

import asyncio
from collections.abc import Iterator
from typing import Any, Final

import httpx
import pytest

from shelfdrop.clients.torrents.qbittorrent import QbittorrentClient
from shelfdrop.clients.torrents.types import TorrentInfo
from shelfdrop.clients.torrents.webui import PLACED_TAG
from shelfdrop.utils.torrent import torrent_id
from tests.integration.support import (
    UP_TIMEOUT_SECONDS,
    FakeSources,
    Stack,
    compose,
    prowlarr_download_stub,
    prowlarr_release,
    prowlarr_search_stub,
    published,
    run_search,
    wait_for_download,
)
from tests.unit.support import torrent_file

pytestmark = [pytest.mark.torrents, pytest.mark.torrent_qbittorrent]

SERVICE: Final = "qbittorrent"
PROFILE: Final = "torrent-qbittorrent"
# qBittorrent as the API reaches it, on the network of the stack.
ADDRESS: Final = "http://qbittorrent:8080"
# The account of docker/qbittorrent/qBittorrent.conf (F64).
USERNAME: Final = "admin"
PASSWORD: Final = "qbittorrent-password-of-the-tests"
CATEGORIES: Final = ("manga", "ebook", "audiobook", "shelfdrop-manual")


@pytest.fixture(scope="module")
def qbittorrent(stack: Stack, media: None) -> Iterator[str]:
    """qBittorrent started for this module on the volume of the placement worker, removed at
    its end: its address published on the loopback."""
    up = compose(
        stack.project,
        "--profile",
        PROFILE,
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
        yield published(stack.project, SERVICE, "8080")
    finally:
        compose(stack.project, "--profile", PROFILE, "rm", "--stop", "--force", SERVICE)


@pytest.fixture
def qbittorrent_chosen(client: httpx.Client, qbittorrent: str) -> Iterator[None]:
    """qBittorrent saved as the torrent client, then qui again with nothing saved."""
    saved = {
        "values": {
            "torrent.client": "qbittorrent",
            "torrent.url": ADDRESS,
            "torrent.username": USERNAME,
        },
        "secrets": {"torrent.password": PASSWORD},
    }
    client.put("/api/v1/settings", json=saved).raise_for_status()
    yield
    cleared = {
        "values": {"torrent.client": "qui", "torrent.url": None, "torrent.username": None},
        "secrets": {"torrent.password": None},
    }
    client.put("/api/v1/settings", json=cleared).raise_for_status()


def webui(address: str) -> httpx.Client:
    """A client of the WebUI API of qBittorrent at `address`, signed in."""
    http = httpx.Client(base_url=address, timeout=30.0, headers={"Referer": f"{address}/"})
    login = {"username": USERNAME, "password": PASSWORD}
    http.post("/api/v2/auth/login", data=login).raise_for_status()
    return http


def probe(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/v1/settings/test", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


@pytest.mark.usefixtures("qbittorrent_chosen")
def test_the_connection_names_the_categories_it_misses_then_finds_them(
    client: httpx.Client, qbittorrent: str
) -> None:
    before = probe(client, {"service": "torrent"})
    with webui(qbittorrent) as http:
        for name in CATEGORIES:
            form = {"category": name, "savePath": f"/data/torrents/{name}"}
            created = http.post("/api/v2/torrents/createCategory", data=form)
            assert created.status_code == 200, created.text
    after = probe(client, {"service": "torrent"})
    wrong = probe(client, {"service": "torrent", "url": ADDRESS, "secret": "a-wrong-password"})

    assert (before["ok"], before["state"], before["version"]) == (True, "connected", "5.3.0")
    assert (before["count"], before["missing"]) == (0, list(CATEGORIES))
    assert (after["ok"], after["count"], after["missing"]) == (True, len(CATEGORIES), [])
    assert (wrong["ok"], wrong["state"], wrong["status"]) == (False, "refused", 401)


@pytest.mark.usefixtures("qbittorrent_chosen")
def test_a_release_sent_is_listed_by_its_hash_and_marked_placed(
    client: httpx.Client, fake_sources: FakeSources, qbittorrent: str
) -> None:
    name = "Shelfdrop Qbittorrent Test.cbz"
    data = torrent_file(name)
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_search_stub(
                "shelfdrop qbittorrent test",
                [7030],
                [
                    prowlarr_release(
                        "https://c411.test/t/9601",
                        "Shelfdrop.Qbittorrent.Test.CBZ",
                        "qbittorrent-1",
                        indexer_id=4,
                        indexer="C411",
                    )
                ],
            ),
            prowlarr_download_stub(4, "qbittorrent-1", data),
        ]
    )
    search = run_search(
        client,
        {
            "mode": "manual",
            "kind": "manga",
            "title": "shelfdrop qbittorrent test",
            "names": ["shelfdrop qbittorrent test"],
        },
    )
    body = {
        "search_id": search["progress"]["id"],
        "work_id": "ignored",
        "author": "ignored",
        "series": "ignored",
        "releases": [{"id": search["releases"][0]["id"], "volumes": {"kind": "unknown"}}],
    }

    sent = client.post("/api/v1/downloads", json=body)

    assert sent.status_code == 200, sent.text
    created = sent.json()["downloads"][0]
    # Found by its hash in the real qBittorrent: sent, stalled shown as downloading.
    shown = wait_for_download(
        client, created["id"], lambda d: d["progress"]["state"] == "downloading"
    )
    assert shown["category"] == "shelfdrop-manual"

    async def listed_then_marked() -> tuple[list[TorrentInfo], list[TorrentInfo]]:
        """Through the connector itself, from the tests, at the published address."""
        async with httpx.AsyncClient(timeout=30.0) as http:
            torrents = QbittorrentClient(http, qbittorrent, USERNAME, PASSWORD)
            before = await torrents.torrents([digest])
            await torrents.mark_placed([digest])
            return before, await torrents.torrents([digest])

    before, after = asyncio.run(listed_then_marked())

    assert before == [
        TorrentInfo(
            hash=digest,
            name=name,
            status="stalled",
            progress=0.0,
            speed=0,
            eta=None,
            category="shelfdrop-manual",
            # The default folder of qBittorrent, in the volume of the placement worker: a
            # category gives its folder to a torrent of the automatic management alone (F63).
            content_path=f"/data/torrents/{name}",
        )
    ]
    assert [t.placed for t in after] == [True]
    with webui(qbittorrent) as http:
        listed = http.get("/api/v2/torrents/info", params={"hashes": digest}).json()
    assert listed[0]["tags"] == PLACED_TAG
