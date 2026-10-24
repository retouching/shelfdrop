"""TorrentClients: the connector of the torrent client chosen in the settings, built again at each
use (a change of client or of its address needs no restart), and the registry of the connectors.

A new connector is one module of this package (a class that follows `TorrentClient`, built by a
`Connector`) and one line of `CONNECTORS`, under the name of the setting `torrent.client`.
"""

from collections.abc import Mapping, Sequence
from typing import Final, Protocol

import httpx

from shelfdrop.clients.exceptions import ServiceNotConfiguredError
from shelfdrop.clients.torrents.client import Connector, TorrentClient, TorrentConnection
from shelfdrop.clients.torrents.qui import QuiClient
from shelfdrop.clients.torrents.transmission import TransmissionClient
from shelfdrop.clients.torrents.types import TorrentCheck, TorrentInfo

# The connectors, by the name of the setting `torrent.client`. A client the settings know but no
# connector serves yet (shelfdrop.settings.catalog.CLIENTS) gets `UnavailableClient`.
CONNECTORS: Final[Mapping[str, Connector]] = {
    "qui": QuiClient.of,
    "transmission": TransmissionClient.of,
}


class ClientUnavailableError(ServiceNotConfiguredError):
    """The client chosen has no connector in this version of shelfdrop."""


class ConnectionSource(Protocol):
    """The settings of the torrent client, read at each use."""

    async def torrent(self) -> TorrentConnection: ...


class UnavailableClient:
    """The client chosen when no connector serves it: every call raises ClientUnavailableError,
    as a client without its address."""

    def __init__(self, client: str) -> None:
        self.client = client

    def unavailable(self) -> ClientUnavailableError:
        return ClientUnavailableError(f"no connector for {self.client}")

    async def version(self) -> str:
        raise self.unavailable()

    async def check(self, categories: Sequence[str]) -> TorrentCheck:
        raise self.unavailable()

    async def add(
        self,
        *,
        category: str,
        file: bytes | None = None,
        magnet: str | None = None,
        directory: str | None = None,
    ) -> None:
        raise self.unavailable()

    async def torrents(self, hashes: Sequence[str]) -> list[TorrentInfo]:
        if not hashes:
            return []
        raise self.unavailable()

    async def mark_placed(self, hashes: Sequence[str]) -> None:
        raise self.unavailable()


class TorrentClients:
    """A container singleton, on the HTTP client of the torrent clients."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        settings: ConnectionSource,
        connectors: Mapping[str, Connector] = CONNECTORS,
    ) -> None:
        self.http = http
        self.settings = settings
        self.connectors = connectors

    async def current(self) -> TorrentClient:
        """The connector of the client saved in the settings, on what is saved now."""
        return self.of(await self.settings.torrent())

    def of(self, connection: TorrentConnection) -> TorrentClient:
        """The connector of `connection` (the test of a connection typed on the page)."""
        connector = self.connectors.get(connection.client)
        if connector is None:
            return UnavailableClient(connection.client)
        return connector(self.http, connection)

    def available(self) -> frozenset[str]:
        """The clients a connector serves."""
        return frozenset(self.connectors)
