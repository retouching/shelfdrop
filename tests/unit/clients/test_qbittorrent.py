"""shelfdrop.clients.qbittorrent: the WebUI API v2 through the client proxy of qui."""

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.utils.torrent import torrent_id
from tests.unit.clients.support import FakeQui
from tests.unit.support import torrent_file

URL = "http://qui.test:7476"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_client(qui: FakeQui) -> QBittorrentClient:
    return QBittorrentClient(httpx.AsyncClient(transport=httpx.MockTransport(qui)))


@pytest.mark.anyio
async def test_the_version_and_the_categories_go_through_the_proxy_of_its_key() -> None:
    qui = FakeQui(categories=["manga", "ebook", "tv"])
    client = new_client(qui)

    version = await client.version(URL, FakeQui.KEY)
    categories = await client.categories(URL, FakeQui.KEY)

    assert version == "5.1.2"
    assert categories == ["ebook", "manga", "tv"]
    assert [r.url.path for r in qui.requests] == [
        f"/proxy/{FakeQui.KEY}/api/v2/app/version",
        f"/proxy/{FakeQui.KEY}/api/v2/torrents/categories",
    ]


@pytest.mark.anyio
async def test_a_wrong_key_is_refused_and_a_missing_one_asks_nothing() -> None:
    qui = FakeQui()
    client = new_client(qui)

    with pytest.raises(ServiceError) as refused:
        await client.version(URL, "wrong")
    with pytest.raises(ServiceNotConfiguredError):
        await client.version(URL, None)

    assert refused.value.refused
    assert len(qui.requests) == 1


@pytest.mark.anyio
async def test_a_torrent_is_added_into_its_category_and_read_by_its_hash() -> None:
    qui = FakeQui(added_as={"state": "downloading", "progress": 0.42, "dlspeed": 2048, "eta": 96})
    client = new_client(qui)
    data = torrent_file("Berserk T01.cbz")
    digest = torrent_id(data)
    assert digest is not None

    assert await client.torrents(URL, FakeQui.KEY, [digest]) == []
    await client.add(URL, FakeQui.KEY, category="manga", file=data)
    found = await client.torrents(URL, FakeQui.KEY, [digest, "f" * 40])

    assert [(t.hash, t.state, t.progress, t.speed, t.eta, t.category) for t in found] == [
        (digest, "downloading", 0.42, 2048, 96, "manga")
    ]
    assert qui.added[0]["torrents"] == data
    add = next(r for r in qui.requests if r.method == "POST")
    assert add.url.path == f"/proxy/{FakeQui.KEY}/api/v2/torrents/add"
    assert add.headers["Content-Type"].startswith("multipart/form-data")
    info = qui.requests[-1]
    assert info.url.params["hashes"] == f"{digest}|{'f' * 40}"


@pytest.mark.anyio
async def test_a_magnet_link_is_added_as_a_link() -> None:
    qui = FakeQui()
    client = new_client(qui)
    magnet = "magnet:?xt=urn:btih:" + "c" * 40

    await client.add(URL, FakeQui.KEY, category="shelfdrop-manual", magnet=magnet)

    assert qui.added == [{"category": b"shelfdrop-manual", "urls": magnet.encode()}]
    assert "c" * 40 in qui.torrents


@pytest.mark.anyio
async def test_a_torrent_refused_or_a_qbittorrent_down_is_a_service_error() -> None:
    qui = FakeQui(refuse=True)
    client = new_client(qui)

    with pytest.raises(ServiceError, match="refused"):
        await client.add(URL, FakeQui.KEY, category="manga", file=torrent_file("x"))
    qui.down = True
    with pytest.raises(ServiceError) as down:
        await client.torrents(URL, FakeQui.KEY, ["a" * 40])
    assert down.value.status == 502
    # No hash, no request.
    assert await client.torrents(URL, FakeQui.KEY, []) == []


@pytest.mark.anyio
async def test_a_torrent_gives_its_content_path_and_takes_a_tag() -> None:
    qui = FakeQui()
    qui.torrents["ab" * 20] = {
        "hash": "ab" * 20,
        "name": "Berserk T01",
        "state": "stalledUP",
        "progress": 1.0,
        "content_path": "/data/torrents/manga/Berserk T01.cbz",
    }
    client = new_client(qui)

    [info] = await client.torrents(URL, FakeQui.KEY, ["ab" * 20])
    await client.add_tags(URL, FakeQui.KEY, ["ab" * 20], "placé")

    assert info.content_path == "/data/torrents/manga/Berserk T01.cbz"
    assert qui.torrents["ab" * 20]["tags"] == "placé"
    tagged = qui.requests[-1]
    assert tagged.method == "POST"
    assert tagged.headers["Content-Type"] == "application/x-www-form-urlencoded"
