"""DownloadService: the releases of a search sent to qBittorrent, the downloads as the page shows
them (with the figures of qBittorrent), and a send tried again."""

import logging
from collections.abc import Sequence
from typing import Protocol

import anyio
import anyio.to_thread

from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.clients.types import TorrentInfo
from shelfdrop.downloads.exceptions import (
    DownloadNotFoundError,
    NotAutomaticError,
    NotRetryableError,
    UnknownReleasesError,
)
from shelfdrop.downloads.repository import DownloadRepository
from shelfdrop.downloads.sender import DownloadEvents, DownloadSender, QbittorrentAddress
from shelfdrop.downloads.states import category_of, completion_event, is_complete, progress_of
from shelfdrop.downloads.types import (
    Download,
    DownloadMode,
    DownloadOptions,
    DownloadView,
    NewDownload,
    SendOrder,
)
from shelfdrop.releases.types import Release, ReleaseSearch, Volumes
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)


class ReleaseFinder(Protocol):
    """The releases of a search kept, scored and ranked as the page shows them."""

    async def read(self, search_id: str) -> ReleaseSearch: ...


class DownloadService:
    """Async throughout: the client of qBittorrent and the sender are async singletons; the
    repository runs in the threadpool."""

    def __init__(
        self,
        repository: DownloadRepository,
        sender: DownloadSender,
        qbittorrent: QBittorrentClient,
        address: QbittorrentAddress,
        finder: ReleaseFinder,
        options: DownloadOptions,
        clock: Clock,
        events: DownloadEvents,
    ) -> None:
        self.repository = repository
        self.sender = sender
        self.qbittorrent = qbittorrent
        self.address = address
        self.finder = finder
        self.options = options
        self.clock = clock
        self.events = events

    async def send(self, order: SendOrder, actor: str) -> list[DownloadView]:
        """The releases of a search sent to qBittorrent, each a download of its own. The
        releases of the search of a work are automatic downloads, those of a manual search
        manual ones. Raises SearchNotFoundError, UnknownReleasesError, and NotAutomaticError
        for a release an automatic download may not take: nothing is sent then."""
        search = await self.finder.read(order.search_id)
        mode: DownloadMode = "auto" if search.progress.mode == "work" else "manual"
        found = {r.id: r for r in search.releases if r.download_url is not None}
        choices = list({c.release_id: c for c in order.choices}.values())
        unknown = [c.release_id for c in choices if c.release_id not in found]
        if unknown:
            raise UnknownReleasesError(unknown)
        if mode == "auto":
            refused = [c.release_id for c in choices if not found[c.release_id].automatic]
            if refused:
                raise NotAutomaticError(refused)
        now = int(self.clock.now())
        orders = [
            self.new_download(found[c.release_id], c.volumes, order, search, mode, now, actor)
            for c in choices
        ]
        created = await anyio.to_thread.run_sync(self.add_all, orders)
        self.sender.start(d.id for d in created)
        return [DownloadView(download=d, progress=progress_of(d, None)) for d in created]

    def new_download(
        self,
        release: Release,
        volumes: Volumes,
        order: SendOrder,
        search: ReleaseSearch,
        mode: DownloadMode,
        now: int,
        actor: str,
    ) -> NewDownload:
        """A download of `release`: the work of an automatic one, its author and its series as
        the page gives them; a manual one names the text searched alone, placed by hand."""
        kind = search.progress.kind
        return NewDownload(
            release_id=release.id,
            guid=release.guid,
            title=release.title,
            indexer_id=release.indexer_id,
            indexer=release.indexer,
            size=release.size,
            download_url=release.download_url or "",
            work_id=order.work_id if mode == "auto" else None,
            work_name=search.progress.title,
            author=order.author if mode == "auto" else "",
            series=order.series if mode == "auto" else "",
            volumes=volumes,
            kind=kind,
            mode=mode,
            category=category_of(kind, mode),
            created_at=now,
            created_by=actor,
        )

    def add_all(self, orders: Sequence[NewDownload]) -> list[Download]:
        created = [self.repository.add(o) for o in orders]
        self.repository.commit()
        return created

    async def read(self) -> list[DownloadView]:
        """The newest downloads, each as qBittorrent has it now: a download qBittorrent has all
        of is completed from now on. qBittorrent down: the downloads sent wait."""
        downloads = await anyio.to_thread.run_sync(self.repository.read_recent, self.options.listed)
        hashes = [d.info_hash for d in downloads if d.stage == "sent" and d.info_hash]
        torrents: dict[str, TorrentInfo] = {}
        if hashes:
            url, api_key = await self.address.qbittorrent()
            try:
                torrents = {
                    t.hash: t for t in await self.qbittorrent.torrents(url, api_key, hashes)
                }
            except ServiceError as exc:
                logger.info("qBittorrent did not answer", extra={"error": type(exc).__name__})
        complete = [
            d
            for d in downloads
            if d.stage == "sent" and d.info_hash in torrents and is_complete(torrents[d.info_hash])
        ]
        if complete:
            await anyio.to_thread.run_sync(self.complete, complete)
        return [
            DownloadView(
                download=d,
                progress=progress_of(d, torrents.get(d.info_hash or "")),
            )
            for d in downloads
        ]

    def complete(self, downloads: list[Download]) -> None:
        now = int(self.clock.now())
        done = set(self.repository.mark_completed([d.id for d in downloads], now))
        self.repository.commit()
        for download in downloads:
            if download.id in done:
                self.events.record(completion_event(download, now))

    async def retry(self, download_id: int) -> DownloadView:
        """The same torrent sent again, into the same category: one more attempt. Raises
        DownloadNotFoundError, NotRetryableError (a duplicate, or a send that did not fail)."""
        download = await anyio.to_thread.run_sync(self.mark_retried, download_id)
        self.sender.start([download.id])
        return DownloadView(download=download, progress=progress_of(download, None))

    def mark_retried(self, download_id: int) -> Download:
        download = self.repository.read(download_id)
        if download is None:
            raise DownloadNotFoundError
        if download.stage != "failed" or download.failure != "not_received":
            raise NotRetryableError
        self.repository.mark_retried(download_id)
        self.repository.commit()
        retried = self.repository.read(download_id)
        if retried is None:
            raise DownloadNotFoundError
        return retried
