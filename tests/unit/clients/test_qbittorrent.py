"""shelfdrop.clients.qbittorrent: the WebUI API v2 through the client proxy of qui."""

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.qbittorrent import QBittorrentClient
from tests.unit.clients.support import FakeQui

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
