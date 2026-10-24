"""PlacementService: the automatic downloads complete put on the shelf, their metadata locked in
Jellyfin, and the writes the API asks for in the libraries. The placement worker alone runs it: it
is the one process that writes there."""

import logging
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import Protocol

import anyio
import anyio.to_thread

from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.clients.types import JellyfinLibrary
from shelfdrop.downloads.covers import DownloadCovers
from shelfdrop.downloads.repository import DownloadRepository, DownloadRepositoryFactory
from shelfdrop.downloads.sender import volume_numbers
from shelfdrop.downloads.states import completion_event, is_complete
from shelfdrop.downloads.types import Download
from shelfdrop.journal.types import NewEvent
from shelfdrop.placement.audio import AudioError, AudioTools
from shelfdrop.placement.layout import (
    AudioVolume,
    Laid,
    NotPlacedError,
    Order,
    lay_audio,
    place_books,
    place_comics,
)
from shelfdrop.placement.metadata import locked_item
from shelfdrop.placement.paths import destination_label, library_of, to_jellyfin, to_local
from shelfdrop.placement.repository import PlacementRepository, PlacementRepositoryFactory
from shelfdrop.placement.shelf import files_of, remove_links, replace_with, write_new
from shelfdrop.placement.types import (
    PLACED_TAG,
    PlacedFile,
    PlacementOptions,
    ShelfFile,
    Unplaced,
)
from shelfdrop.works.types import Clock, Kind

logger = logging.getLogger(__name__)

# What a failure of the placement is, in the journal: a link refused, a merge failed.
FAILURES: frozenset[Unplaced] = frozenset({"link_refused", "merge_failed"})


class PlacementSettings(Protocol):
    """The settings the placement reads at each round."""

    async def qbittorrent(self) -> tuple[str | None, str | None]: ...

    async def jellyfin(self) -> tuple[str | None, str | None]: ...

    async def libraries(self) -> dict[Kind, str]: ...

    async def merge_mp3(self) -> bool: ...

    async def covers(self) -> bool: ...

    async def lock_jellyfin(self) -> bool: ...


class CoverSource(Protocol):
    """The cover of a work at its sources (the work search)."""

    async def cover(self, work_id: str) -> bytes | None: ...


class PlacementEvents(Protocol):
    def record(self, event: NewEvent) -> None: ...


def read_shelved(
    repository: PlacementRepository, *, work_id: str | None, series: str, kind: Kind
) -> list[ShelfFile]:
    return repository.read_shelved(work_id, series, kind)


def mark_task(repository: PlacementRepository, *, task_id: int, state: str, now: int) -> None:
    repository.mark_task(task_id, state, now)


def order_of(download: Download) -> Order:
    return Order(
        download_id=download.id,
        kind=download.kind,
        work_id=download.work_id,
        series=download.series or download.work_name,
        author=download.author,
        release=download.title,
        volumes=download.volumes,
    )


class PlacementService:
    def __init__(
        self,
        repositories: PlacementRepositoryFactory,
        downloads: DownloadRepositoryFactory,
        qbittorrent: QBittorrentClient,
        jellyfin: JellyfinClient,
        settings: PlacementSettings,
        tools: AudioTools,
        covers: CoverSource,
        events: PlacementEvents,
        clock: Clock,
        options: PlacementOptions,
        download_covers: DownloadCovers,
    ) -> None:
        self.repositories = repositories
        self.downloads = downloads
        self.qbittorrent = qbittorrent
        self.jellyfin = jellyfin
        self.settings = settings
        self.tools = tools
        self.covers = covers
        self.events = events
        self.clock = clock
        self.options = options
        self.download_covers = download_covers
        self.percents: dict[int, int] = {}

    async def round(self) -> None:
        """One round of the worker: the downloads complete, then placed; the metadata of the
        files placed locked; the writes asked for."""
        await self.complete()
        for download in await self.on_downloads(lambda r: r.read_to_place(), commit=False):
            await self.place(download)
        await self.lock()
        await self.run_tasks()

    async def complete(self) -> None:
        """The downloads qBittorrent has all of are complete (whether the page reads them or
        not); each end once in the journal, with the cover of its work."""
        sent = await self.on_downloads(lambda r: r.read_sent(), commit=False)
        hashes = [d.info_hash for d in sent if d.info_hash]
        if not hashes:
            return
        url, api_key = await self.settings.qbittorrent()
        try:
            torrents = {t.hash: t for t in await self.qbittorrent.torrents(url, api_key, hashes)}
        except ServiceError as exc:
            logger.info("qBittorrent did not answer", extra={"error": type(exc).__name__})
            return
        complete = [
            d for d in sent if d.info_hash in torrents and is_complete(torrents[d.info_hash])
        ]
        if not complete:
            return
        now = int(self.clock.now())
        done = set(
            await self.on_downloads(lambda r: r.mark_completed([d.id for d in complete], now))
        )
        for download in complete:
            if download.id in done:
                event = await self.download_covers.dress(download, completion_event(download, now))
                await anyio.to_thread.run_sync(self.events.record, event)

    async def place(self, download: Download) -> None:
        """A download complete put on the shelf, or left to Ranger with its reason; a download
        of which some files have no volume it can read is placed in part, and left to Ranger
        (`no_volume`) for the rest."""
        order = order_of(download)
        try:
            laid, library = await self.lay(download, order)
        except NotPlacedError as exc:
            await self.unplaced(download, exc.reason, exc.placed)
            return
        if laid.unknown:
            # The volumes it read placed, the rest left to Ranger: the download stays to place
            # (no `placed` yet, no tag) until Ranger links or ignores the rest.
            await self.unplaced(download, "no_volume", laid.files)
            await self.refresh_library(library)
            return
        destination = destination_label(order.kind, order.series, library)
        now = int(self.clock.now())
        await self.on_shelf(lambda r: r.add_files(laid.files, now))
        await self.on_downloads(lambda r: r.mark_placed(download.id, destination, now))
        logger.info("Download placed", extra={"download": download.id, "files": len(laid.files)})
        await self.after_placement(download, library)
        placed = NewEvent(
            type="placed",
            group=f"placed:{download.created_by}:{download.created_at}:{order.series}",
            facts={
                "destination": destination,
                "volumes": list(laid.volumes) or volume_numbers(download),
                "skipped": list(laid.present),
            },
            cover=laid.cover,
        )
        await anyio.to_thread.run_sync(self.events.record, placed)

    async def lay(self, download: Download, order: Order) -> tuple[Laid, JellyfinLibrary | None]:
        """The files of the torrent laid on the shelf. Raises NotPlacedError."""
        url, api_key = await self.settings.qbittorrent()
        try:
            torrents = await self.qbittorrent.torrents(url, api_key, [download.info_hash or ""])
        except ServiceError as exc:
            logger.info("qBittorrent did not answer", extra={"error": type(exc).__name__})
            raise NotPlacedError("missing_files") from exc
        if not torrents or not torrents[0].content_path:
            raise NotPlacedError("missing_files")
        files = await anyio.to_thread.run_sync(files_of, Path(torrents[0].content_path))
        if not files:
            raise NotPlacedError("missing_files")
        roots = await self.settings.libraries()
        root = Path(roots[order.kind])
        library = await self.library_for(roots[order.kind])
        match order.kind:
            case "manga":
                covers = await self.settings.covers()
                laid = await anyio.to_thread.run_sync(place_comics, order, files, root, covers)
            case "ebook":
                laid = await anyio.to_thread.run_sync(place_books, order, files, root)
            case "audiobook":
                laid = await self.place_audio(download.id, order, files, root)
        if not laid.files and not laid.present:
            raise NotPlacedError("no_files")
        return laid, library

    async def place_audio(
        self, download_id: int | None, order: Order, files: Sequence[Path], root: Path
    ) -> Laid:
        """The tracks of each volume merged into one M4B with its cover (the picture of the
        torrent, else the one of the tracks, else the one of the sources); the tracks of the
        shelf removed once merged. A merge that fails leaves the tracks in place. Raises
        NotPlacedError."""
        merge = await self.settings.merge_mp3()
        laid, merges = await anyio.to_thread.run_sync(lay_audio, order, files, root, merge)
        placed = list(laid.files)
        cover: bytes | None = None
        for volume in merges:
            picture = volume.cover or await self.find_cover(order, volume)
            try:
                await self.tools.merge(
                    volume.tracks,
                    volume.title,
                    picture,
                    volume.target,
                    lambda percent: self.progress(download_id, percent),
                )
            except (AudioError, FileExistsError) as exc:
                logger.warning("Merge failed", extra={"error": type(exc).__name__})
                raise NotPlacedError("merge_failed", placed) from exc
            await anyio.to_thread.run_sync(remove_links, list(volume.tracks))
            placed.append(
                PlacedFile(
                    download_id=order.download_id,
                    kind=order.kind,
                    work_id=order.work_id,
                    series=order.series,
                    author=order.author,
                    volume=volume.volume,
                    chapter=None,
                    path=str(volume.target),
                )
            )
            if picture is not None and cover is None:
                cover = await anyio.to_thread.run_sync(picture.read_bytes)
        return Laid(
            folder=laid.folder,
            files=tuple(placed),
            volumes=tuple(sorted({p.volume for p in placed if p.volume is not None})),
            present=laid.present,
            cover=cover,
        )

    async def find_cover(self, order: Order, volume: AudioVolume) -> Path | None:
        """The picture of the tracks, else the cover of the work at its sources, written as
        `cover.jpg` in the folder of the volume."""
        target = volume.folder / "cover.jpg"
        if await self.tools.embedded_cover(volume.tracks[0], target):
            return target
        if order.work_id is None:
            return None
        data = await self.covers.cover(order.work_id)
        if data is None:
            return None
        await anyio.to_thread.run_sync(write_new, target, data)
        return target if target.is_file() else None

    def progress(self, download_id: int | None, percent: int) -> None:
        """The percent of a merge for the page, every 5 percent (a short write of the loop)."""
        if download_id is not None and percent >= self.percents.get(download_id, -5) + 5:
            self.percents[download_id] = percent
            self.write_downloads(lambda r: r.mark_placing(download_id, percent))

    async def unplaced(
        self, download: Download, reason: Unplaced, placed: Sequence[PlacedFile]
    ) -> None:
        now = int(self.clock.now())
        if placed:
            await self.on_shelf(lambda r: r.add_files(placed, now))
        await self.on_downloads(lambda r: r.mark_unplaced(download.id, reason, now))
        logger.info("Download left to Ranger", extra={"download": download.id, "reason": reason})
        facts: dict[str, str] = {
            "work": download.series or download.work_name,
            "release": download.title,
            "reason": reason,
        }
        group = f"{download.created_by}:{download.created_at}"
        await anyio.to_thread.run_sync(
            self.events.record, NewEvent(type="to_place", group=f"to_place:{group}", facts=facts)
        )
        if reason in FAILURES:
            failed = NewEvent(
                type="failed",
                group=f"failed:{reason}:{group}",
                facts={"what": reason, "release": download.title, "error": reason},
            )
            await anyio.to_thread.run_sync(self.events.record, failed)

    async def after_placement(self, download: Download, library: JellyfinLibrary | None) -> None:
        """The tag `placé` in qBittorrent (another tool that places may leave it alone), and the
        new files scanned by Jellyfin; neither failure undoes the placement."""
        url, api_key = await self.settings.qbittorrent()
        try:
            await self.qbittorrent.add_tags(url, api_key, [download.info_hash or ""], PLACED_TAG)
        except ServiceError as exc:
            logger.info("Tag not set", extra={"error": type(exc).__name__})
        await self.refresh_library(library)

    async def refresh_library(self, library: JellyfinLibrary | None) -> None:
        """The new files of `library` scanned by Jellyfin; a failure undoes nothing."""
        if library is None or library.item_id is None:
            return
        url, api_key = await self.settings.jellyfin()
        try:
            await self.jellyfin.refresh(url, api_key, library.item_id, "new")
        except ServiceError as exc:
            logger.info("Jellyfin did not scan", extra={"error": type(exc).__name__})

    async def library_for(self, root: str) -> JellyfinLibrary | None:
        url, api_key = await self.settings.jellyfin()
        try:
            return library_of(root, await self.jellyfin.libraries(url, api_key))[0]
        except (ServiceError, LookupError):
            return None

    async def lock(self) -> int:
        """The files placed whose items Jellyfin now holds: their name, series, number and
        authors set and locked. Returns how many."""
        if not await self.settings.lock_jellyfin():
            return 0
        since = int(self.clock.now()) - self.options.lock_seconds
        unlocked = await self.on_shelf(lambda r: r.read_unlocked(since), commit=False)
        if not unlocked:
            return 0
        url, api_key = await self.settings.jellyfin()
        roots = await self.settings.libraries()
        done: list[int] = []
        try:
            libraries = await self.jellyfin.libraries(url, api_key)
            for kind in sorted({f.kind for f in unlocked}):
                library, location = library_of(roots[kind], libraries)
                if library.item_id is None:
                    continue
                items = await self.jellyfin.items(
                    url, api_key, library.item_id, ("Book", "AudioBook")
                )
                by_path = {item.path: item for item in items}
                for placed in (f for f in unlocked if f.kind == kind):
                    item = by_path.get(to_jellyfin(placed.path, roots[kind], location))
                    if item is None:
                        continue
                    shelved = await self.on_shelf(
                        partial(
                            read_shelved,
                            work_id=placed.work_id,
                            series=placed.series,
                            kind=placed.kind,
                        ),
                        commit=False,
                    )
                    volumes = sorted(
                        {s.volume for s in shelved if s.volume is not None and s.chapter is None}
                    )
                    body = await self.jellyfin.item(url, api_key, item.id)
                    await self.jellyfin.update_item(
                        url, api_key, item.id, locked_item(body, placed, volumes)
                    )
                    done.append(placed.id)
        except (ServiceError, LookupError) as exc:
            logger.info("Metadata not locked", extra={"error": type(exc).__name__})
        if done:
            await self.on_shelf(lambda r: r.mark_locked(done))
        return len(done)

    async def run_tasks(self) -> None:
        """The `cover.jpg` the page chose, written in the folder of its series."""
        tasks = [
            t
            for t in await self.on_shelf(lambda r: r.read_tasks(), commit=False)
            if t.kind == "cover"
        ]
        if not tasks:
            return
        url, api_key = await self.settings.jellyfin()
        roots = await self.settings.libraries()
        try:
            libraries = await self.jellyfin.libraries(url, api_key)
        except ServiceError as exc:
            logger.info("Jellyfin did not answer", extra={"error": type(exc).__name__})
            return
        for task in tasks:
            now = int(self.clock.now())
            try:
                folder = Path(to_local(task.path, roots, libraries))
                if not await anyio.to_thread.run_sync(folder.is_dir):
                    raise LookupError(task.path)
                await anyio.to_thread.run_sync(replace_with, folder / "cover.jpg", task.data)
            except (LookupError, OSError) as exc:
                logger.info("Cover not written", extra={"error": type(exc).__name__})
                await self.on_shelf(partial(mark_task, task_id=task.id, state="failed", now=now))
                continue
            await self.on_shelf(partial(mark_task, task_id=task.id, state="done", now=now))

    def write_downloads(self, use: Callable[[DownloadRepository], None]) -> None:
        repository = self.downloads()
        try:
            use(repository)
            repository.commit()
        finally:
            repository.close()

    async def on_downloads[T](
        self, use: Callable[[DownloadRepository], T], *, commit: bool = True
    ) -> T:
        def run() -> T:
            repository = self.downloads()
            try:
                result = use(repository)
                if commit:
                    repository.commit()
                return result
            finally:
                repository.close()

        return await anyio.to_thread.run_sync(run)

    async def on_shelf[T](
        self, use: Callable[[PlacementRepository], T], *, commit: bool = True
    ) -> T:
        def run() -> T:
            repository = self.repositories()
            try:
                result = use(repository)
                if commit:
                    repository.commit()
                return result
            finally:
                repository.close()

        return await anyio.to_thread.run_sync(run)
