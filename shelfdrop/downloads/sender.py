"""DownloadSender: the sends to qBittorrent of every request (a container singleton).

A send outlives its request: its torrent is fetched through Prowlarr (or the one a first send
read is taken again), its id read (`shelfdrop.utils.torrent`), then qBittorrent is asked for
it: a torrent it already has, never added by shelfdrop, is a duplicate. Otherwise it is added
into its category, and looked for by its hash, `tries` times `check_seconds` apart (qBittorrent
may accept a torrent and lose it): found, it is sent; never found, not received. `parallel`
torrents are fetched and added at a time.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine, Iterable
from typing import Any, Protocol

import anyio
import anyio.to_thread

from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.downloads.repository import DownloadRepository, DownloadRepositoryFactory
from shelfdrop.downloads.types import Download, DownloadOptions, Failure
from shelfdrop.releases.exceptions import ProwlarrError
from shelfdrop.releases.types import Torrent
from shelfdrop.utils.torrent import magnet_id, torrent_id
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)


class TorrentSource(Protocol):
    """Prowlarr: the torrent behind the download link of a release."""

    async def torrent(self, link: str) -> Torrent: ...


class QbittorrentAddress(Protocol):
    """The address of qui and the key of its client proxy, read at each use (the settings)."""

    async def qbittorrent(self) -> tuple[str | None, str | None]: ...


class SendFailedError(Exception):
    """A send ends without the torrent in qBittorrent; `failure` says why."""

    def __init__(self, failure: Failure) -> None:
        super().__init__(failure)
        self.failure = failure


def id_of(torrent: Torrent) -> str | None:
    if torrent.file is not None:
        return torrent_id(torrent.file)
    return None if torrent.magnet is None else magnet_id(torrent.magnet)


class DownloadSender:
    def __init__(
        self,
        source: TorrentSource,
        qbittorrent: QBittorrentClient,
        address: QbittorrentAddress,
        repositories: DownloadRepositoryFactory,
        options: DownloadOptions,
        clock: Clock,
    ) -> None:
        self.source = source
        self.qbittorrent = qbittorrent
        self.address = address
        self.repositories = repositories
        self.options = options
        self.clock = clock
        self.slots = asyncio.Semaphore(options.parallel)
        self.sending: set[int] = set()
        self.tasks: set[asyncio.Task[None]] = set()

    def start(self, download_ids: Iterable[int]) -> None:
        """Send these downloads (each `sending`), unless a send of one already runs."""
        for download_id in download_ids:
            if download_id not in self.sending:
                self.sending.add(download_id)
                self.spawn(self.send(download_id))

    async def resume(self) -> None:
        """At start: send again the downloads a stop left `sending`."""
        self.start(await self.read(lambda r: r.read_sending()))

    async def idle(self) -> None:
        """Wait for every send running to end."""
        while self.tasks:
            await asyncio.gather(*self.tasks)

    async def close(self) -> None:
        """Stop the sends running; they stay `sending`, and `resume` sends them again."""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    def spawn(self, coroutine: Coroutine[Any, Any, None]) -> None:
        task = asyncio.get_running_loop().create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def send(self, download_id: int) -> None:
        try:
            download = await self.read(lambda r: r.read(download_id))
            if download is None or download.stage != "sending":
                return
            try:
                await self.deliver(download)
            except SendFailedError as exc:
                failure = exc.failure
                logger.info("Download not sent", extra={"download": download_id, "reason": failure})
                await self.write(lambda r: r.mark_failed(download_id, failure))
                return
            now = int(self.clock.now())
            await self.write(lambda r: r.mark_sent(download_id, now))
            logger.info("Download sent", extra={"download": download_id})
        finally:
            self.sending.discard(download_id)

    async def deliver(self, download: Download) -> None:
        """Raises SendFailedError."""
        url, api_key = await self.address.qbittorrent()
        async with self.slots:
            torrent, digest = await self.torrent_of(download)
            try:
                present = await self.qbittorrent.torrents(url, api_key, [digest])
                if present:
                    if download.added_at is None:
                        raise SendFailedError("duplicate")
                    # Added by an earlier attempt: received after all.
                    return
                await self.qbittorrent.add(
                    url,
                    api_key,
                    category=download.category,
                    file=torrent.file,
                    magnet=torrent.magnet,
                )
            except ServiceError as exc:
                logger.info("qBittorrent refused a torrent", extra={"error": type(exc).__name__})
                raise SendFailedError("not_received") from exc
            now = int(self.clock.now())
            await self.write(lambda r: r.mark_added(download.id, now))
        for attempt in range(self.options.tries):
            if attempt:
                await anyio.sleep(self.options.check_seconds)
            try:
                if await self.qbittorrent.torrents(url, api_key, [digest]):
                    return
            except ServiceError as exc:
                logger.info("qBittorrent did not answer", extra={"error": type(exc).__name__})
        raise SendFailedError("not_received")

    async def torrent_of(self, download: Download) -> tuple[Torrent, str]:
        """The torrent an earlier attempt read, or the one Prowlarr gives now, and its id.
        Raises SendFailedError."""
        torrent = await self.read(lambda r: r.read_torrent(download.id))
        if torrent is None:
            if not download.download_url:
                raise SendFailedError("not_received")
            try:
                torrent = await self.source.torrent(download.download_url)
            except ProwlarrError as exc:
                logger.info("Prowlarr gave no torrent", extra={"error": type(exc).__name__})
                raise SendFailedError("not_received") from exc
        digest = id_of(torrent)
        if digest is None:
            logger.info("Not a torrent", extra={"download": download.id})
            raise SendFailedError("not_received")
        await self.write(lambda r: r.save_torrent(download.id, torrent, digest))
        return torrent, digest

    def run[T](self, use: Callable[[DownloadRepository], T], commit: bool) -> T:
        """`use` on a repository of its own, in the threadpool, committed with `commit`."""
        repository = self.repositories()
        try:
            result = use(repository)
            if commit:
                repository.commit()
            return result
        finally:
            repository.close()

    async def read[T](self, use: Callable[[DownloadRepository], T]) -> T:
        return await anyio.to_thread.run_sync(self.run, use, False)

    async def write(self, use: Callable[[DownloadRepository], None]) -> None:
        await anyio.to_thread.run_sync(self.run, use, True)
