"""shelfdrop.clients.torrents.factory: the connector of the client saved, built again at each use;
a client no connector serves."""

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceNotConfiguredError
from shelfdrop.clients.torrents.client import TorrentClient, TorrentConnection
from shelfdrop.clients.torrents.factory import (
    CONNECTORS,
    ClientUnavailableError,
    TorrentClients,
    UnavailableClient,
)
from shelfdrop.clients.torrents.qui import QuiClient
from shelfdrop.settings.catalog import CLIENTS
from shelfdrop.settings.types import TorrentSettings
from tests.unit.clients.support import (
    QUI_URL,
    FakeQui,
    FakeTorrentSettings,
    qui_settings,
    torrent_clients,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_every_connector_serves_a_client_the_settings_know() -> None:
    assert set(CONNECTORS) <= set(CLIENTS)
    assert "qui" in CONNECTORS


@pytest.mark.anyio
async def test_the_connector_follows_the_settings_at_each_use() -> None:
    qui = FakeQui()
    settings = FakeTorrentSettings(qui_settings(url=None))
    torrents = torrent_clients(qui, settings)

    with pytest.raises(ServiceNotConfiguredError):
        await (await torrents.current()).version()
    # Saved since: the next use reads it, without a restart.
    settings.connection = qui_settings()
    client = await torrents.current()

    assert isinstance(client, QuiClient)
    assert await client.version() == "5.1.2"
    assert qui.requests[0].url.host == "qui.test"


@pytest.mark.anyio
async def test_a_client_no_connector_serves_answers_nothing_and_asks_nothing() -> None:
    qui = FakeQui()
    settings = FakeTorrentSettings(
        TorrentSettings(
            client="transmission", url=QUI_URL, username="admin", password="p", api_key=None
        )
    )
    client = await torrent_clients(qui, settings).current()

    assert isinstance(client, UnavailableClient)
    with pytest.raises(ClientUnavailableError):
        await client.check(["manga"])
    with pytest.raises(ClientUnavailableError):
        await client.add(category="manga", magnet="magnet:?xt=urn:btih:" + "c" * 40)
    with pytest.raises(ClientUnavailableError):
        await client.torrents(["a" * 40])
    with pytest.raises(ClientUnavailableError):
        await client.mark_placed(["a" * 40])
    # Nothing to look for, nothing to refuse: as a client asked for no hash.
    assert await client.torrents([]) == []
    assert qui.requests == []


@pytest.mark.anyio
async def test_a_connector_registered_is_built_on_the_connection() -> None:
    built: list[TorrentConnection] = []

    def connector(http: httpx.AsyncClient, connection: TorrentConnection) -> TorrentClient:
        built.append(connection)
        return QuiClient(http, connection.url, "key-of-the-test")

    torrents = TorrentClients(
        httpx.AsyncClient(transport=httpx.MockTransport(FakeQui())),
        FakeTorrentSettings(),
        {"deluge": connector},
    )
    deluge = TorrentSettings(
        client="deluge", url=QUI_URL, username=None, password="p", api_key=None
    )

    assert isinstance(torrents.of(deluge), QuiClient)
    assert built == [deluge]
    assert isinstance(torrents.of(qui_settings()), UnavailableClient)
    assert torrents.available() == frozenset({"deluge"})
