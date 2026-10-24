"""ConnectionProbes: the test of the connection of each service and of each metadata source,
with the values typed on the page or those saved. A container singleton.

- Prowlarr: `GET /api/v1/system/status`, then its indexers on.
- The torrent client (its connector, `shelfdrop.clients.torrents`): its version, then the
  categories of shelfdrop (and what keeps shelfdrop from sending to it), with the client, the
  address, the username and the secret given.
- Jellyfin: `GET /System/Info` with the key, then its libraries of books.
- A metadata source: one fixed search ("Chainsaw Man" for the manga, "Can't Hurt Me" for the
  books), and the time of its answer.
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Final

import anyio

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.torrents.factory import ClientUnavailableError, TorrentClients
from shelfdrop.releases.clients.prowlarr import ProwlarrClient, fixed
from shelfdrop.releases.exceptions import ProwlarrError, ProwlarrNotConfiguredError
from shelfdrop.settings.catalog import CLIENTS, torrent_secret
from shelfdrop.settings.reader import SettingsReader
from shelfdrop.settings.types import ProbeResult
from shelfdrop.works.clients.myanimelist import MyAnimeListClient
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.service import MetadataClient, WorkSources
from shelfdrop.works.types import Family

# The categories of the torrent client shelfdrop downloads into.
CATEGORIES: Final = ("manga", "ebook", "audiobook", "shelfdrop-manual")
# The fixed search of a source, by family.
SEARCHES: Final = {"manga": "Chainsaw Man", "book": "Can't Hurt Me"}
# A source that has not answered after this many seconds is unavailable (the search gives it
# as long).
SOURCE_SECONDS: Final = 5.0


def failure(service: str, exc: ServiceError | ProwlarrError) -> ProbeResult:
    if isinstance(exc, ServiceNotConfiguredError | ProwlarrNotConfiguredError):
        return ProbeResult(service=service, state="no_key")
    if exc.status in (401, 403):
        return ProbeResult(service=service, state="refused", status=exc.status)
    return ProbeResult(service=service, state="unavailable", status=exc.status)


def credentials_missing(client: str, username: str | None, secret: str | None) -> bool:
    """A credential `client` signs in with is missing: the key of qui, the username and the
    password of qBittorrent, the password of Deluge; Transmission signs in with both, or with
    none."""
    match client:
        case "qui" | "deluge":
            return not secret
        case "qbittorrent":
            return not (username and secret)
        case _:
            return bool(username) != bool(secret)


def constant(value: str | None) -> Callable[[], Awaitable[str | None]]:
    async def read() -> str | None:
        return value

    return read


class ConnectionProbes:
    def __init__(
        self,
        prowlarr: ProwlarrClient,
        torrents: TorrentClients,
        jellyfin: JellyfinClient,
        sources: WorkSources,
        saved: SettingsReader,
    ) -> None:
        self.prowlarr = prowlarr
        self.torrents = torrents
        self.jellyfin = jellyfin
        self.saved = saved
        self.sources: dict[str, MetadataClient] = {
            client.name: client for client in sources.clients
        }

    def names(self) -> tuple[str, ...]:
        """Every service and source a test knows."""
        return ("prowlarr", "torrent", "jellyfin", *self.sources)

    def clients(self) -> tuple[str, ...]:
        """The torrent clients a connector serves, in the order of the catalog."""
        available = self.torrents.available()
        return tuple(client for client in CLIENTS if client in available)

    async def run(
        self,
        service: str,
        url: str | None,
        secret: str | None,
        *,
        client: str | None = None,
        username: str | None = None,
    ) -> ProbeResult:
        """The test of `service` with this address and this secret; the torrent client: the
        client `client` and the username `username` (None: those saved, a `username` "": none).
        Raises KeyError for a service it does not know."""
        match service:
            case "torrent":
                return await self.run_torrent(url, secret, client, username)
            case "prowlarr" | "jellyfin" if not url:
                return ProbeResult(service=service, state="no_address")
            case "prowlarr" | "jellyfin" if not secret:
                return ProbeResult(service=service, state="no_key")
            case "prowlarr":
                return await self.run_prowlarr(url, secret)
            case "jellyfin":
                return await self.run_jellyfin(url, secret)
            case _:
                return await self.run_source(self.sources[service], secret)

    async def run_prowlarr(self, url: str | None, secret: str | None) -> ProbeResult:
        client = ProwlarrClient(self.prowlarr.http, fixed(url, secret))
        try:
            version = await client.version()
            indexers = await client.indexers()
        except ProwlarrError as exc:
            return failure("prowlarr", exc)
        on = [i for i in indexers if i.enabled and i.protocol in ("torrent", "")]
        return ProbeResult(service="prowlarr", state="connected", version=version, count=len(on))

    async def run_torrent(
        self, url: str | None, secret: str | None, client: str | None, username: str | None
    ) -> ProbeResult:
        """The client `client` (None: the one saved), at the address `url`, signed in with
        `username` (None: the one saved, "": none) and `secret` (the key of qui, the password of
        the others)."""
        saved = await self.saved.torrent()
        chosen = saved.client if client is None else client
        connection = replace(
            saved,
            client=chosen,
            url=url,
            username=saved.username if username is None else (username or None),
        )
        if torrent_secret(chosen) == "torrent.api_key":
            connection = replace(connection, api_key=secret)
        else:
            connection = replace(connection, password=secret)
        if not url:
            return ProbeResult(service="torrent", state="no_address", client=chosen)
        if chosen not in self.torrents.available():
            # A client the settings know, that no connector of this version serves.
            return ProbeResult(service="torrent", state="no_connector", client=chosen)
        if credentials_missing(chosen, connection.username, secret):
            return ProbeResult(service="torrent", state="no_key", client=chosen)
        try:
            check = await self.torrents.of(connection).check(CATEGORIES)
        except ClientUnavailableError:
            return ProbeResult(service="torrent", state="no_connector", client=chosen)
        except ServiceError as exc:
            return replace(failure("torrent", exc), client=chosen)
        if check.unsupported is not None:
            return ProbeResult(
                service="torrent",
                state="unsupported",
                version=check.version,
                client=chosen,
                reason=check.unsupported,
            )
        return ProbeResult(
            service="torrent",
            state="connected",
            version=check.version,
            count=len(CATEGORIES) - len(check.missing),
            missing=check.missing,
            client=chosen,
        )

    async def run_jellyfin(self, url: str | None, secret: str | None) -> ProbeResult:
        try:
            version = await self.jellyfin.server_version(url, secret)
            libraries = await self.jellyfin.libraries(url, secret)
        except ServiceError as exc:
            return failure("jellyfin", exc)
        books = [library for library in libraries if library.collection_type == "books"]
        return ProbeResult(service="jellyfin", state="connected", version=version, count=len(books))

    async def run_source(self, client: MetadataClient, secret: str | None) -> ProbeResult:
        if isinstance(client, MyAnimeListClient):
            if not secret:
                return ProbeResult(service=client.name, state="no_key")
            client = MyAnimeListClient(client.http, constant(secret))
        family: Family = "manga" if "manga" in client.families else "book"
        started = time.monotonic()
        try:
            with anyio.fail_after(SOURCE_SECONDS):
                await client.search(SEARCHES[family], family)
        except TimeoutError:
            return ProbeResult(service=client.name, state="unavailable")
        except SourceError as exc:
            status = str(exc).removeprefix("HTTP ")
            return ProbeResult(
                service=client.name,
                state="unavailable",
                status=int(status) if status.isdigit() else None,
            )
        elapsed = int((time.monotonic() - started) * 1000)
        return ProbeResult(service=client.name, state="connected", elapsed_ms=elapsed)
