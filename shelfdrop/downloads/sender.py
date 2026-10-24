"""DownloadSender: the sends to the torrent client of every request (a container singleton).

A send outlives its request: its torrent is fetched through Prowlarr (or the one a first send
read is taken again), its id read (`shelfdrop.utils.torrent`), then the torrent client chosen in
the settings is asked for it: a torrent it already has, never added by shelfdrop, is a
duplicate. Otherwise it is added into its category (and the folder of its kind, when the
settings give one), and looked for by its hash, `tries` times `check_seconds` apart (a client
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
from shelfdrop.clients.torrents.factory import TorrentClients
from shelfdrop.downloads.covers import DownloadCovers
from shelfdrop.downloads.repository import DownloadRepository, DownloadRepositoryFactory
from shelfdrop.downloads.types import Download, DownloadOptions, Failure
from shelfdrop.journal.types import NewEvent
from shelfdrop.releases.exceptions import ProwlarrError
from shelfdrop.releases.types import Torrent
from shelfdrop.utils.torrent import magnet_id, torrent_id
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)


class TorrentSource(Protocol):
    """Prowlarr: the torrent behind the download link of a release."""

    async def torrent(self, link: str) -> Torrent: ...


class TorrentFolders(Protocol):
    """The folder of the torrent client of each kind of download (`manga`, `ebook`,
    `audiobook`, `manual`) that has one, read at each send (the settings)."""

    async def torrent_folders(self) -> dict[str, str]: ...


class DownloadEvents(Protocol):
    """The journal: a torrent sent (with the cover of its work, for an automatic one), not
    received, sent again."""

    def record(self, event: NewEvent) -> None: ...


def volume_numbers(download: Download) -> list[int]:
    """The volumes of a download, as numbers: none for a whole series or unknown volumes."""
    volumes = download.volumes
    if volumes.first is None:
        return []
    last = volumes.last if volumes.last is not None else volumes.first
    return list(range(volumes.first, max(volumes.first, last) + 1))[:500]


def sent_event(download: Download) -> NewEvent:
    """The downloads sent by one request make one message: same account, same second, same
    work."""
    return NewEvent(
        type="sent",
        group=f"sent:{download.created_by}:{download.created_at}:{download.work_name}",
        facts={
            "work": download.series or download.work_name,
            "volumes": volume_numbers(download),
            "tracker": download.indexer,
            "size": download.size,
            "mode": download.mode,
            "actor": download.created_by,
        },
    )


def outcome_event(download: Download, failure: Failure | None, client: str) -> NewEvent | None:
    """The event of the end of a send: sent, not received (`failed`), or, for a retry, the
    retry and its result, with the torrent client (`client`, the setting `torrent.client`). A
    duplicate has none."""
    if failure == "duplicate":
        return None
    if download.attempts > 1:
        return NewEvent(
            type="retry",
            group=f"retry:{download.id}:{download.attempts}",
            facts={
                "work": download.series or download.work_name,
                "release": download.title,
                "attempt": download.attempts,
                "result": failure or "sent",
                "client": client,
            },
        )
    if failure is None:
        return sent_event(download)
    return NewEvent(
        type="failed",
        group=f"failed:not_received:{download.created_by}:{download.created_at}",
        facts={"what": "not_received", "release": download.title, "client": client},
    )


class SendFailedError(Exception):
    """A send ends without the torrent in the torrent client; `failure` says why."""

    def __init__(self, failure: Failure) -> None:
        super().__init__(failure)
        self.failure = failure


def folder_of(download: Download, folders: dict[str, str]) -> str | None:
    """The folder of the client of the kind of `download` (`manual` for a manual one)."""
    return folders.get("manual" if download.mode == "manual" else download.kind)


def id_of(torrent: Torrent) -> str | None:
    if torrent.file is not None:
        return torrent_id(torrent.file)
    return None if torrent.magnet is None else magnet_id(torrent.magnet)


class DownloadSender:
    def __init__(
        self,
        source: TorrentSource,
        torrents: TorrentClients,
        folders: TorrentFolders,
        repositories: DownloadRepositoryFactory,
        options: DownloadOptions,
        clock: Clock,
        events: DownloadEvents,
        covers: DownloadCovers,
    ) -> None:
        self.source = source
        self.torrents = torrents
        self.folders = folders
        self.repositories = repositories
        self.options = options
        self.clock = clock
        self.events = events
        self.covers = covers
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
            failure: Failure | None = None
            try:
                await self.deliver(download)
            except SendFailedError as exc:
                failure = exc.failure
                refused: Failure = exc.failure
                logger.info("Download not sent", extra={"download": download_id, "reason": failure})
                await self.write(lambda r: r.mark_failed(download_id, refused))
            else:
                now = int(self.clock.now())
                await self.write(lambda r: r.mark_sent(download_id, now))
                logger.info("Download sent", extra={"download": download_id})
            client = (await self.torrents.settings.torrent()).client
            event = outcome_event(download, failure, client)
            if event is not None:
                event = await self.covers.dress(download, event)
                await anyio.to_thread.run_sync(self.events.record, event)
        finally:
            self.sending.discard(download_id)

    async def deliver(self, download: Download) -> None:
        """Raises SendFailedError."""
        client = await self.torrents.current()
        directory = folder_of(download, await self.folders.torrent_folders())
        async with self.slots:
            torrent, digest = await self.torrent_of(download)
            try:
                present = await client.torrents([digest])
                if present:
                    if download.added_at is None:
                        raise SendFailedError("duplicate")
                    # Added by an earlier attempt: received after all.
                    return
                await client.add(
                    category=download.category,
                    file=torrent.file,
                    magnet=torrent.magnet,
                    directory=directory,
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
                if await client.torrents([digest]):
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
