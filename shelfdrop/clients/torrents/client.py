"""The contract of a connector of a torrent client, shared by the factory, every connector and
every domain that calls one (the sends, their follow-up, the placement, the test of the
connection): it lives here, not in one of them.

A connector is built for one connection (`TorrentConnection`, read from the settings at each use
by `TorrentClients`); it raises `ServiceNotConfiguredError` when the connection misses what it
needs, `ServiceError` when the client does not answer or refuses.
"""

from collections.abc import Callable, Sequence
from typing import Protocol

import httpx

from shelfdrop.clients.torrents.types import TorrentCheck, TorrentInfo


class TorrentConnection(Protocol):
    """The settings of the torrent client: which one, where, and how to sign in. A connector
    reads the fields its client needs and leaves the others."""

    @property
    def client(self) -> str:
        """`qui`, `qbittorrent`, `deluge`, `transmission` (the setting `torrent.client`)."""
        ...

    @property
    def url(self) -> str | None: ...

    @property
    def username(self) -> str | None: ...

    @property
    def password(self) -> str | None: ...

    @property
    def api_key(self) -> str | None: ...


class TorrentClient(Protocol):
    async def version(self) -> str:
        """The version of the client, without a leading `v`."""
        ...

    async def check(self, categories: Sequence[str]) -> TorrentCheck:
        """The test of the connection: the version, the `categories` the client misses, and
        why shelfdrop could not send to it."""
        ...

    async def add(
        self,
        *,
        category: str,
        file: bytes | None = None,
        magnet: str | None = None,
        directory: str | None = None,
    ) -> None:
        """A `.torrent` file or a magnet link added into `category`, downloaded into
        `directory` (None: where the client puts that category). Raises ServiceError when it
        refuses it; the torrent may still be lost after: the caller looks for it by its hash."""
        ...

    async def torrents(self, hashes: Sequence[str]) -> list[TorrentInfo]:
        """The torrents of these hashes the client has (none asked for no hash)."""
        ...

    async def mark_placed(self, hashes: Sequence[str]) -> None:
        """The mark of shelfdrop on what it placed (the tag `placé` of qBittorrent), for
        another tool that places. A client that cannot mark a torrent does nothing."""
        ...


type Connector = Callable[[httpx.AsyncClient, TorrentConnection], TorrentClient]
"""How a connector is built: the HTTP client of the torrent clients, and the connection."""
