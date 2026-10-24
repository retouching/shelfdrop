"""shelfdrop.clients.torrents.qui: the WebUI API v2 of qBittorrent through the client proxy of
qui."""

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.qui import QuiClient
from shelfdrop.clients.torrents.types import TorrentInfo
from shelfdrop.utils.torrent import torrent_id
from tests.unit.clients.support import QUI_URL as URL
from tests.unit.clients.support import FakeQui, multipart_fields
from tests.unit.support import torrent_file


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_client(qui: FakeQui, url: str | None = URL, key: str | None = FakeQui.KEY) -> QuiClient:
    return QuiClient(httpx.AsyncClient(transport=httpx.MockTransport(qui)), url, key)


@pytest.mark.anyio
async def test_the_version_and_the_categories_go_through_the_proxy_of_its_key() -> None:
    qui = FakeQui(categories=["manga", "ebook", "tv"])
    client = new_client(qui)

    version = await client.version()
    check = await client.check(["manga", "ebook", "audiobook", "shelfdrop-manual"])

    assert version == "5.1.2"
    assert check.version == "5.1.2"
    assert check.missing == ("audiobook", "shelfdrop-manual")
    assert check.unsupported is None
    assert [r.url.path for r in qui.requests] == [
        f"/proxy/{FakeQui.KEY}/api/v2/app/version",
        f"/proxy/{FakeQui.KEY}/api/v2/app/version",
        f"/proxy/{FakeQui.KEY}/api/v2/torrents/categories",
    ]


@pytest.mark.anyio
async def test_a_wrong_key_is_refused_and_a_missing_one_asks_nothing() -> None:
    qui = FakeQui()

    with pytest.raises(ServiceError) as refused:
        await new_client(qui, key="wrong").version()
    with pytest.raises(ServiceNotConfiguredError):
        await new_client(qui, key=None).version()
    with pytest.raises(ServiceNotConfiguredError):
        await new_client(qui, url=None).version()

    assert refused.value.refused
    assert len(qui.requests) == 1


@pytest.mark.anyio
async def test_a_torrent_is_added_into_its_category_and_read_by_its_hash() -> None:
    qui = FakeQui(added_as={"state": "downloading", "progress": 0.42, "dlspeed": 2048, "eta": 96})
    client = new_client(qui)
    data = torrent_file("Berserk T01.cbz")
    digest = torrent_id(data)
    assert digest is not None

    assert await client.torrents([digest]) == []
    await client.add(category="manga", file=data)
    found = await client.torrents([digest, "f" * 40])

    assert found == [
        TorrentInfo(
            hash=digest,
            name=digest,
            status="downloading",
            progress=0.42,
            speed=2048,
            eta=96,
            category="manga",
        )
    ]
    assert qui.added[0]["torrents"] == data
    assert "savepath" not in qui.added[0]
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

    await client.add(category="shelfdrop-manual", magnet=magnet)

    assert qui.added == [{"category": b"shelfdrop-manual", "urls": magnet.encode()}]
    assert "c" * 40 in qui.torrents


@pytest.mark.anyio
async def test_a_folder_given_is_the_save_path_of_the_torrent() -> None:
    qui = FakeQui()
    client = new_client(qui)

    await client.add(category="audiobook", file=torrent_file("x"), directory="/data/audio")

    add = next(r for r in qui.requests if r.method == "POST")
    assert multipart_fields(add)["savepath"] == b"/data/audio"


@pytest.mark.anyio
async def test_a_torrent_refused_or_a_qbittorrent_down_is_a_service_error() -> None:
    qui = FakeQui(refuse=True)
    client = new_client(qui)

    with pytest.raises(ServiceError, match="refused"):
        await client.add(category="manga", file=torrent_file("x"))
    with pytest.raises(ServiceError, match="no torrent"):
        await client.add(category="manga")
    qui.down = True
    with pytest.raises(ServiceError) as down:
        await client.torrents(["a" * 40])
    assert down.value.status == 502
    # No hash, no request.
    requests = len(qui.requests)
    assert await client.torrents([]) == []
    await client.mark_placed([])
    assert len(qui.requests) == requests


@pytest.mark.anyio
async def test_a_torrent_gives_its_content_path_and_takes_the_mark_of_shelfdrop() -> None:
    qui = FakeQui()
    qui.torrents["ab" * 20] = {
        "hash": "ab" * 20,
        "name": "Berserk T01",
        "state": "stalledUP",
        "progress": 1.0,
        "content_path": "/data/torrents/manga/Berserk T01.cbz",
    }
    client = new_client(qui)

    [info] = await client.torrents(["ab" * 20])
    await client.mark_placed(["ab" * 20])
    [marked] = await client.torrents(["ab" * 20])

    assert info.content_path == "/data/torrents/manga/Berserk T01.cbz"
    assert info.status == "complete"
    assert not info.placed
    assert marked.placed
    assert qui.torrents["ab" * 20]["tags"] == "placé"
    tagged = qui.requests[-2]
    assert tagged.method == "POST"
    assert tagged.url.path == f"/proxy/{FakeQui.KEY}/api/v2/torrents/addTags"
    assert tagged.headers["Content-Type"] == "application/x-www-form-urlencoded"
