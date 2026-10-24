"""HandPlacement: the files of Ranger, run by the placement
worker after each round: the downloads left to Ranger listed with their files, what the page
asked done (a volume, a file of chapters, a release in chapters linked to its volumes), and the
scan of the libraries for the files misplaced, every day and when the page asks."""

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Protocol

import anyio
import anyio.to_thread

from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.clients.types import JellyfinLibrary
from shelfdrop.downloads.types import Download
from shelfdrop.journal.types import NewEvent
from shelfdrop.placement.chapters import (
    HandLaid,
    loose_chapters,
    place_chapter,
    place_chapters,
    place_volume,
)
from shelfdrop.placement.existing import content_of
from shelfdrop.placement.items import chapter_numbers, items_of
from shelfdrop.placement.layout import NotPlacedError, Order, place_books
from shelfdrop.placement.naming import safe
from shelfdrop.placement.paths import destination_label
from shelfdrop.placement.repository import PlacementRepository
from shelfdrop.placement.scan import scan_library
from shelfdrop.placement.service import PlacementService
from shelfdrop.placement.shelf import files_of, names_in
from shelfdrop.placement.types import (
    LIBRARY_NAMES,
    ChapterRequest,
    ChaptersRequest,
    IgnoreRequest,
    NewItem,
    PlacedFile,
    PlaceItem,
    ShelfFile,
    VolumeRequest,
)
from shelfdrop.placement.uploads import lay_upload, remove_empty, remove_upload, upload_items
from shelfdrop.releases.types import Volumes
from shelfdrop.uploads.repository import UploadRepository, UploadRepositoryFactory
from shelfdrop.uploads.store import UploadStore
from shelfdrop.uploads.types import UploadState
from shelfdrop.works.types import Kind

logger = logging.getLogger(__name__)

DAY = 24 * 3600


class HandSettings(Protocol):
    """The settings the files of Ranger read at each round."""

    async def scan_time(self) -> tuple[int, int]: ...

    async def uploads_folder(self) -> str: ...

    async def upload_keep_days(self) -> int: ...


def sized(paths: Sequence[Path]) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for path in paths:
        try:
            found.append((str(path), path.stat().st_size))
        except OSError:
            continue
    return found


def volumes_in(folder: Path) -> tuple[int, ...]:
    return tuple(sorted(content_of(names_in(folder)).volumes))


def shelf_of(folder: Path, files: Sequence[str]) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """The volumes of a series folder, and its chapters loose but in `files`."""
    return volumes_in(folder), loose_chapters(folder, files)


def inode_of(path: str) -> tuple[int, int] | None:
    try:
        found = Path(path).stat()
    except OSError:
        return None
    return found.st_dev, found.st_ino


def not_shelved(files: Sequence[tuple[str, int]], shelved: Sequence[str]) -> list[tuple[str, int]]:
    """The files of a torrent but those already on the shelf: a hardlink shares their inode."""
    placed = {n for n in (inode_of(p) for p in shelved) if n is not None}
    if not placed:
        return list(files)
    return [(path, size) for path, size in files if inode_of(path) not in placed]


def remove_sources(paths: Sequence[str], kept: set[str]) -> None:
    """The files of the libraries now on the shelf under another name: removed."""
    for path in paths:
        if path not in kept:
            Path(path).unlink(missing_ok=True)


def add_items(repository: PlacementRepository, *, items: Sequence[NewItem], now: int) -> None:
    for item in items:
        repository.add_item(item, now)


def update_items(
    repository: PlacementRepository, *, items: Sequence[tuple[int, NewItem]], now: int
) -> None:
    for item_id, item in items:
        repository.update_item(item_id, item, now)


def set_shelf(
    repository: PlacementRepository,
    *,
    item_id: int,
    existing: tuple[int, ...],
    loose: tuple[float, ...],
) -> None:
    repository.set_item_shelf(item_id, existing, loose)


def download_files(repository: PlacementRepository, *, download_id: int) -> list[ShelfFile]:
    return repository.read_download_files(download_id)


def mark_upload(
    repository: UploadRepository, *, upload_id: int, state: UploadState, now: int
) -> None:
    repository.mark(upload_id, state, now)


def mark_done(repository: PlacementRepository, *, task_id: int, now: int) -> None:
    repository.mark_task(task_id, "done", now)


def scan_slot(now: float, hour: int, minute: int) -> float:
    """The last time of the day of the scan (local time) at or before `now`."""
    local = datetime.fromtimestamp(now).astimezone()
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()
    return slot if slot <= now else slot - DAY


class HandPlacement:
    def __init__(
        self,
        placement: PlacementService,
        settings: HandSettings,
        uploads: UploadRepositoryFactory,
        store: UploadStore,
    ) -> None:
        self.placement = placement
        self.settings = settings
        self.uploads = uploads
        self.store = store

    async def round(self) -> None:
        await self.collect()
        await self.take_uploads()
        await self.refresh_shelf()
        await self.run_requests()
        await self.tidy_uploads()
        await self.scan_when_due()

    async def on_uploads[T](
        self, use: Callable[[UploadRepository], T], *, commit: bool = True
    ) -> T:
        def run() -> T:
            repository = self.uploads()
            try:
                result = use(repository)
                if commit:
                    repository.commit()
                return result
            finally:
                repository.close()

        return await anyio.to_thread.run_sync(run)

    async def take_uploads(self) -> int:
        """The files sent and checked, moved into the folder of the uploads and listed in
        Ranger, a ZIP opened. Returns how many."""
        verified = await self.on_uploads(lambda r: r.read_in(("verified",)), commit=False)
        if not verified:
            return 0
        root = Path(await self.settings.uploads_folder())
        for upload in verified:
            source = self.store.file(upload.id, upload.name)
            now = int(self.placement.clock.now())
            try:
                files = await anyio.to_thread.run_sync(lay_upload, source, root / str(upload.id))
            except OSError as exc:
                logger.info(
                    "Upload not taken", extra={"upload": upload.id, "error": type(exc).__name__}
                )
                await self.on_uploads(
                    partial(mark_upload, upload_id=upload.id, state="lost", now=now)
                )
                continue
            items = upload_items(upload.name, files)
            await self.placement.on_shelf(partial(add_items, items=items, now=now))
            await self.on_uploads(
                partial(mark_upload, upload_id=upload.id, state="listed", now=now)
            )
            await anyio.to_thread.run_sync(self.store.remove, upload.id)
            logger.info("Upload listed in Ranger", extra={"upload": upload.id, "files": len(items)})
        return len(verified)

    async def tidy_uploads(self) -> None:
        """The files sent left in Ranger longer than `uploads.keep_days`, and the uploads that
        stopped as long ago, removed; the folders of the uploads left empty too."""
        days = await self.settings.upload_keep_days()
        before = int(self.placement.clock.now()) - days * DAY
        root = Path(await self.settings.uploads_folder())
        old = [
            i
            for i in await self.placement.on_shelf(lambda r: r.read_open_of("upload"), commit=False)
            if i.created_at < before and i.request is None
        ]
        for item in old:
            await anyio.to_thread.run_sync(remove_upload, [*item.files, item.path], root)
        if old:
            await self.placement.on_shelf(lambda r: r.delete_items([i.id for i in old]))
            logger.info("Uploads left in Ranger removed", extra={"files": len(old)})
        stopped = [
            u
            for u in await self.on_uploads(
                lambda r: r.read_in(("receiving", "corrupt", "lost", "listed")), commit=False
            )
            if u.updated_at < before
        ]
        for upload in stopped:
            await anyio.to_thread.run_sync(self.store.remove, upload.id)
        if stopped:
            await self.on_uploads(lambda r: r.delete([u.id for u in stopped]))
        known = await self.on_uploads(lambda r: r.read_ids(), commit=False)
        for upload_id in await anyio.to_thread.run_sync(self.store.upload_ids):
            if upload_id not in known:
                await anyio.to_thread.run_sync(self.store.remove, upload_id)
        await anyio.to_thread.run_sync(remove_empty, root)

    async def collect(self) -> int:
        """The downloads Ranger takes, not listed yet: their files read in the torrent. Returns
        how many."""
        left = await self.placement.on_downloads(lambda r: r.read_left(), commit=False)
        listed = await self.placement.on_shelf(lambda r: r.read_item_downloads(), commit=False)
        todo = [d for d in left if d.id not in listed]
        if not todo:
            return 0
        url, api_key = await self.placement.settings.qbittorrent()
        hashes = [d.info_hash for d in todo if d.info_hash]
        try:
            torrents = {
                t.hash: t
                for t in (
                    await self.placement.qbittorrent.torrents(url, api_key, hashes)
                    if hashes
                    else []
                )
            }
        except ServiceError as exc:
            logger.info("qBittorrent did not answer", extra={"error": type(exc).__name__})
            return 0
        roots = await self.placement.settings.libraries()
        for download in todo:
            info = torrents.get(download.info_hash or "")
            content = info.content_path if info is not None else ""
            shelved = [
                f.path
                for f in await self.placement.on_shelf(
                    partial(download_files, download_id=download.id),
                    commit=False,
                )
            ]
            items = await anyio.to_thread.run_sync(
                self.items_for, download, content, roots, shelved
            )
            now = int(self.placement.clock.now())
            await self.placement.on_shelf(partial(add_items, items=items, now=now))
            logger.info("Download listed in Ranger", extra={"download": download.id})
        return len(todo)

    @staticmethod
    def items_for(
        download: Download, content: str, roots: dict[Kind, str], shelved: Sequence[str] = ()
    ) -> list[NewItem]:
        """The files of Ranger of `download`, but those it put on the shelf already
        (`shelved`: a placement in part, a link refused after others)."""
        files = sized(files_of(Path(content))) if content else []
        files = not_shelved(files, shelved)
        if download.kind != "manga":
            return items_of(download, content, files, ())
        folder = Path(roots["manga"]) / safe(download.series or download.work_name)
        existing, loose = shelf_of(folder, [path for path, _ in files])
        return items_of(download, content, files, existing, loose)

    async def refresh_shelf(self) -> None:
        """The volumes and the loose chapters of the series of each release in chapters left
        in Ranger, read again: the page counts a volume complete as `place_chapters` will."""
        items = [
            i
            for i in await self.placement.on_shelf(
                lambda r: r.read_items(placed=False), commit=False
            )
            if i.state == "chapters" and i.request is None
        ]
        if not items:
            return
        roots = await self.placement.settings.libraries()
        for item in items:
            folder = Path(roots["manga"]) / safe(item.series)
            existing, loose = await anyio.to_thread.run_sync(shelf_of, folder, item.files)
            if (existing, loose) != (item.existing, item.loose):
                await self.placement.on_shelf(
                    partial(set_shelf, item_id=item.id, existing=existing, loose=loose)
                )

    async def run_requests(self) -> None:
        for item in await self.placement.on_shelf(lambda r: r.read_asked(), commit=False):
            await self.run(item)

    async def run(self, item: PlaceItem) -> None:
        """What the page asked for `item`, done; a refusal leaves it in Ranger with its
        reason."""
        request = item.request
        if request is None:
            return
        if isinstance(request, IgnoreRequest):
            await self.ignore(item)
            return
        kind: Kind = request.kind if isinstance(request, VolumeRequest) else "manga"
        roots = await self.placement.settings.libraries()
        root = Path(roots[kind])
        sources = item.files or (item.path,)
        now = int(self.placement.clock.now())
        try:
            hand = await self.lay(item, request, kind, root, sources)
        except NotPlacedError as exc:
            await self.failed(item, exc.reason, exc.placed, now)
            return
        library = await self.placement.library_for(roots[kind])
        destination = destination_label(kind, request.series, library)
        placed = {f.path for f in hand.laid.files}
        if item.origin != "download":
            await anyio.to_thread.run_sync(remove_sources, hand.used, placed)
        removed = [*hand.removed, *(p for p in hand.used if p not in placed)]

        await self.placement.on_shelf(lambda r: r.remove_files(removed))
        await self.placement.on_shelf(lambda r: r.add_files(hand.laid.files, now))
        if hand.left:
            left = hand.left
            await self.placement.on_shelf(
                lambda r: r.mark_item_kept(item.id, left, chapter_numbers(left), now)
            )
        else:
            await self.placement.on_shelf(lambda r: r.mark_item_placed(item.id, destination, now))
        logger.info("File of Ranger placed", extra={"item": item.id, "files": len(placed)})
        await self.after(item, destination, hand, library)

    async def ignore(self, item: PlaceItem) -> None:
        """The file left where it is (a file of a download, of the libraries or sent alike:
        nothing is written nor removed), out of the files to place; its download placed once
        none of its files is left."""
        now = int(self.placement.clock.now())
        await self.placement.on_shelf(lambda r: r.mark_item_ignored(item.id, now))
        logger.info("File of Ranger ignored", extra={"item": item.id})
        if item.download_id is not None:
            await self.close_download(item.download_id, None)

    async def close_download(self, download_id: int, destination: str | None) -> None:
        """The download placed (and tagged) once none of its files is left in Ranger; without a
        `destination`, the one of its files placed, if any."""
        left = await self.placement.on_shelf(
            lambda r: r.count_open_of_download(download_id), commit=False
        )
        download = await self.placement.on_downloads(lambda r: r.read(download_id), commit=False)
        if download is None or left:
            return
        where = destination or await self.destination_of(download)
        now = int(self.placement.clock.now())
        await self.placement.on_downloads(lambda r: r.mark_placed(download_id, where, now))
        await self.placement.after_placement(download, None)

    async def destination_of(self, download: Download) -> str:
        """Where the files of `download` went: the destination of its last file placed from
        Ranger, else the series of a file the worker placed alone; empty when it has none."""
        download_id = download.id
        items = await self.placement.on_shelf(
            lambda r: r.read_items_of_download(download_id), commit=False
        )
        placed = [i.destination for i in items if i.state == "placed" and i.destination]
        if placed:
            return placed[-1]
        files = await self.placement.on_shelf(
            lambda r: r.read_download_files(download_id), commit=False
        )
        if files:
            roots = await self.placement.settings.libraries()
            library = await self.placement.library_for(roots[files[0].kind])
            return destination_label(files[0].kind, files[0].series, library)
        return download.destination or ""

    async def failed(
        self, item: PlaceItem, reason: str, placed: Sequence[PlacedFile], now: int
    ) -> None:
        """The request not done: what it placed before kept, the file left in Ranger with the
        reason."""
        if placed:
            await self.placement.on_shelf(lambda r: r.add_files(placed, now))
        await self.placement.on_shelf(lambda r: r.mark_item_failed(item.id, reason, now))
        logger.info("File of Ranger not placed", extra={"item": item.id, "reason": reason})

    async def lay(
        self,
        item: PlaceItem,
        request: VolumeRequest | ChapterRequest | ChaptersRequest,
        kind: Kind,
        root: Path,
        sources: Sequence[str],
    ) -> HandLaid:
        """The files of `item` on the shelf. Raises NotPlacedError."""
        covers = await self.placement.settings.covers()
        match request:
            case ChapterRequest():
                return await anyio.to_thread.run_sync(place_chapter, sources, request, root, covers)
            case ChaptersRequest():
                return await anyio.to_thread.run_sync(
                    place_chapters, sources, request, root, covers
                )
            case VolumeRequest() if kind == "manga":
                return await anyio.to_thread.run_sync(place_volume, sources, request, root, covers)
            case VolumeRequest():
                volume = request.volume or 1
                order = Order(
                    download_id=item.download_id,
                    kind=kind,
                    work_id=request.work_id,
                    series=request.series,
                    author=request.author,
                    release=item.name,
                    volumes=Volumes(kind="single", first=volume, last=volume),
                    title=request.title or request.series,
                )
                paths = [Path(s) for s in sources]
                if kind == "ebook":
                    laid = await anyio.to_thread.run_sync(place_books, order, paths, root)
                else:
                    laid = await self.placement.place_audio(item.download_id, order, paths, root)
                if not laid.files:
                    raise NotPlacedError("exists" if laid.present else "no_files")
                return HandLaid(laid=laid, used=tuple(sources))

    async def after(
        self, item: PlaceItem, destination: str, hand: HandLaid, library: JellyfinLibrary | None
    ) -> None:
        """The download placed once none of its files is left in Ranger; the library scanned
        by Jellyfin; the event `placed`."""
        if item.download_id is not None:
            await self.close_download(item.download_id, destination)
        await self.placement.refresh_library(library)
        placed = NewEvent(
            type="placed",
            group=f"placed:ranger:{item.id}",
            facts={
                "destination": destination,
                "volumes": list(hand.laid.volumes),
                "skipped": [],
            },
            cover=hand.laid.cover,
        )
        await anyio.to_thread.run_sync(self.placement.events.record, placed)

    async def scan_when_due(self) -> None:
        """The scan the page asked, or the one of the day once its time passed."""
        asked = [
            t
            for t in await self.placement.on_shelf(lambda r: r.read_tasks(), commit=False)
            if t.kind == "scan"
        ]
        if not asked and not await self.is_due():
            return
        await self.scan()
        now = int(self.placement.clock.now())
        for task in asked:
            await self.placement.on_shelf(partial(mark_done, task_id=task.id, now=now))
        if not asked:
            await self.placement.on_shelf(lambda r: r.record_scan(now))

    async def is_due(self) -> bool:
        hour, minute = await self.settings.scan_time()
        slot = scan_slot(self.placement.clock.now(), hour, minute)
        last = await self.placement.on_shelf(lambda r: r.last_scan(), commit=False)
        return last is None or last < slot

    async def scan(self) -> int:
        """The files misplaced of every library in Ranger: new ones added, those gone removed,
        the others read again (but those the page asked for, and those ignored, which stay
        ignored). Returns the new ones."""
        roots = await self.placement.settings.libraries()
        merge = await self.placement.settings.merge_mp3()
        placed = await self.placement.on_shelf(lambda r: r.read_shelf_paths(), commit=False)
        found: list[NewItem] = []
        for kind, root in roots.items():
            found += await anyio.to_thread.run_sync(scan_library, kind, Path(root), placed, merge)
        listed = await self.placement.on_shelf(
            lambda r: r.read_open_of("library", ignored=True), commit=False
        )
        by_path = {i.path: i for i in listed}
        seen = {f.path for f in found}
        new = [f for f in found if f.path not in by_path]
        gone = [i.id for i in listed if i.path not in seen and i.request is None]
        now = int(self.placement.clock.now())

        await self.placement.on_shelf(lambda r: r.delete_items(gone))
        again = [
            (by_path[f.path].id, f)
            for f in found
            if f.path in by_path
            and by_path[f.path].request is None
            and by_path[f.path].state != "ignored"
        ]
        await self.placement.on_shelf(partial(update_items, items=again, now=now))
        await self.placement.on_shelf(partial(add_items, items=new, now=now))
        logger.info("Libraries scanned", extra={"found": len(found), "new": len(new)})
        counts: dict[Kind, int] = {}
        for item in new:
            if item.kind is not None:
                counts[item.kind] = counts.get(item.kind, 0) + 1
        for kind, count in counts.items():
            event = NewEvent(
                type="misplaced",
                group=f"misplaced:{now}",
                facts={"library": LIBRARY_NAMES[kind], "count": count},
            )
            await anyio.to_thread.run_sync(self.placement.events.record, event)
        return len(new)
