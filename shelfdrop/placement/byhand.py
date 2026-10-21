"""HandPlacement: the files of Ranger (plan section 3, points 4 bis and 5), run by the placement
worker after each round: the downloads left to Ranger listed with their files, what the page
asked done (a volume, a file of chapters, a release in chapters linked to its volumes), and the
scan of the libraries for the files misplaced, every day and when the page asks."""

import logging
from collections.abc import Sequence
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
from shelfdrop.placement.chapters import HandLaid, place_chapter, place_chapters, place_volume
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
    NewItem,
    PlacedFile,
    PlaceItem,
    VolumeRequest,
)
from shelfdrop.releases.types import Volumes
from shelfdrop.works.types import Kind

logger = logging.getLogger(__name__)

DAY = 24 * 3600


class HandSettings(Protocol):
    """The settings the files of Ranger read at each round."""

    async def scan_time(self) -> tuple[int, int]: ...


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


def mark_done(repository: PlacementRepository, *, task_id: int, now: int) -> None:
    repository.mark_task(task_id, "done", now)


def scan_slot(now: float, hour: int, minute: int) -> float:
    """The last time of the day of the scan (local time) at or before `now`."""
    local = datetime.fromtimestamp(now).astimezone()
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()
    return slot if slot <= now else slot - DAY


class HandPlacement:
    def __init__(self, placement: PlacementService, settings: HandSettings) -> None:
        self.placement = placement
        self.settings = settings

    async def round(self) -> None:
        await self.collect()
        await self.run_requests()
        await self.scan_when_due()

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
            items = await anyio.to_thread.run_sync(self.items_for, download, content, roots)
            now = int(self.placement.clock.now())
            await self.placement.on_shelf(partial(add_items, items=items, now=now))
            logger.info("Download listed in Ranger", extra={"download": download.id})
        return len(todo)

    @staticmethod
    def items_for(download: Download, content: str, roots: dict[Kind, str]) -> list[NewItem]:
        files = sized(files_of(Path(content))) if content else []
        existing = (
            volumes_in(Path(roots["manga"]) / safe(download.series or download.work_name))
            if download.kind == "manga"
            else ()
        )
        return items_of(download, content, files, existing)

    async def run_requests(self) -> None:
        for item in await self.placement.on_shelf(lambda r: r.read_asked(), commit=False):
            await self.run(item)

    async def run(self, item: PlaceItem) -> None:
        """What the page asked for `item`, done; a refusal leaves it in Ranger with its
        reason."""
        request = item.request
        if request is None:
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
            download_id = item.download_id
            left = await self.placement.on_shelf(
                lambda r: r.count_open_of_download(download_id), commit=False
            )
            download = await self.placement.on_downloads(
                lambda r: r.read(download_id), commit=False
            )
            if download is not None and left == 0:
                now = int(self.placement.clock.now())
                await self.placement.on_downloads(
                    lambda r: r.mark_placed(download_id, destination, now)
                )
                await self.placement.after_placement(download, None)
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
        the others read again (but those the page asked for). Returns the new ones."""
        roots = await self.placement.settings.libraries()
        merge = await self.placement.settings.merge_mp3()
        placed = await self.placement.on_shelf(lambda r: r.read_shelf_paths(), commit=False)
        found: list[NewItem] = []
        for kind, root in roots.items():
            found += await anyio.to_thread.run_sync(scan_library, kind, Path(root), placed, merge)
        listed = await self.placement.on_shelf(lambda r: r.read_open_of("library"), commit=False)
        by_path = {i.path: i for i in listed}
        seen = {f.path for f in found}
        new = [f for f in found if f.path not in by_path]
        gone = [i.id for i in listed if i.path not in seen and i.request is None]
        now = int(self.placement.clock.now())

        await self.placement.on_shelf(lambda r: r.delete_items(gone))
        again = [
            (by_path[f.path].id, f)
            for f in found
            if f.path in by_path and by_path[f.path].request is None
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
