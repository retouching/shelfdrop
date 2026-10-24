"""ConnectionProbes: the test of the connection of each service and of each metadata source,
with the values typed on the page or those saved. A container singleton.

- Prowlarr: `GET /api/v1/system/status`, then its indexers on.
- qBittorrent, through qui: its version, then the categories of shelfdrop.
- Jellyfin: `GET /System/Info` with the key, then its libraries of books.
- A metadata source: one fixed search ("Chainsaw Man" for the manga, "Can't Hurt Me" for the
  books), and the time of its answer.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Final

import anyio

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.releases.clients.prowlarr import ProwlarrClient, fixed
from shelfdrop.releases.exceptions import ProwlarrError, ProwlarrNotConfiguredError
from shelfdrop.settings.types import ProbeResult
from shelfdrop.works.clients.myanimelist import MyAnimeListClient
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.service import MetadataClient, WorkSources
from shelfdrop.works.types import Family

# The categories of qBittorrent shelfdrop downloads into.
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


def constant(value: str | None) -> Callable[[], Awaitable[str | None]]:
    async def read() -> str | None:
        return value

    return read


class ConnectionProbes:
    def __init__(
        self,
        prowlarr: ProwlarrClient,
        qbittorrent: QBittorrentClient,
        jellyfin: JellyfinClient,
        sources: WorkSources,
    ) -> None:
        self.prowlarr = prowlarr
        self.qbittorrent = qbittorrent
        self.jellyfin = jellyfin
        self.sources: dict[str, MetadataClient] = {
            client.name: client for client in sources.clients
        }

    def names(self) -> tuple[str, ...]:
        """Every service and source a test knows."""
        return ("prowlarr", "qbittorrent", "jellyfin", *self.sources)

    async def run(self, service: str, url: str | None, secret: str | None) -> ProbeResult:
        """The test of `service` with this address and this secret. Raises KeyError for a
        service it does not know."""
        match service:
            case "prowlarr" | "qbittorrent" | "jellyfin" if not url:
                return ProbeResult(service=service, state="no_address")
            case "prowlarr" | "qbittorrent" | "jellyfin" if not secret:
                return ProbeResult(service=service, state="no_key")
            case "prowlarr":
                return await self.run_prowlarr(url, secret)
            case "qbittorrent":
                return await self.run_qbittorrent(url, secret)
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

    async def run_qbittorrent(self, url: str | None, secret: str | None) -> ProbeResult:
        try:
            version = await self.qbittorrent.version(url, secret)
            categories = await self.qbittorrent.categories(url, secret)
        except ServiceError as exc:
            return failure("qbittorrent", exc)
        missing = tuple(name for name in CATEGORIES if name not in categories)
        return ProbeResult(
            service="qbittorrent",
            state="connected",
            version=version,
            count=len(CATEGORIES) - len(missing),
            missing=missing,
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
