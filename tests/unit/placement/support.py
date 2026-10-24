"""What the tests of the placement share: the files of the shelf in memory, ffmpeg played by a
fake, the settings, the covers of the sources, and builders of CBZ files."""

import dataclasses
import io
import itertools
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import override

import anyio
import httpx

from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.downloads.covers import DownloadCovers
from shelfdrop.downloads.types import Download, NewDownload
from shelfdrop.placement.audio import AudioError, AudioTools
from shelfdrop.placement.byhand import HandPlacement
from shelfdrop.placement.repository import OPEN, PlacementRepository
from shelfdrop.placement.service import PlacementService
from shelfdrop.placement.types import (
    ItemOrigin,
    ItemState,
    LibraryTask,
    NewItem,
    PlacedFile,
    PlaceItem,
    PlacementOptions,
    PlaceRequest,
    SeriesLink,
    ShelfFile,
    TaskKind,
)
from shelfdrop.releases.types import Volumes
from shelfdrop.uploads.store import UploadStore
from shelfdrop.works.types import Kind
from tests.unit.clients.support import API_KEY, FakeJellyfin, FakeQui, torrent_clients
from tests.unit.downloads.support import FakeDownloadRepository
from tests.unit.support import FakeJournal, no_session
from tests.unit.uploads.support import FakeUploadRepository
from tests.unit.works.support import FixedClock

JELLYFIN_URL = "http://jellyfin.test"
JELLYFIN_KEY = API_KEY
JPEG = b"\xff\xd8\xff\xe0page"


def cbz(path: Path, pages: Sequence[str], *, data: Callable[[str], bytes] | None = None) -> Path:
    """A CBZ at `path` whose pages are named `pages` (each holding its own name)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for page in pages:
            archive.writestr(page, (data or (lambda name: JPEG + name.encode()))(page))
    return path


def pages_in(path: Path) -> list[tuple[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        return [(name, archive.read(name)) for name in archive.namelist()]


def zipped(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class FakePlacementRepository(PlacementRepository):
    """The files of the shelf and the tasks in memory; one instance plays every session."""

    def __init__(self) -> None:
        super().__init__(no_session())
        self.files: list[ShelfFile] = []
        self.tasks: dict[int, tuple[LibraryTask, str]] = {}
        self.ids = itertools.count(1)
        self.items: dict[int, PlaceItem] = {}
        self.scans: list[int] = []
        self.owners: dict[str, int | None] = {}
        self.links: dict[str, SeriesLink] = {}

    @override
    def add_files(self, files: Sequence[PlacedFile], now: int) -> None:
        for placed in files:
            self.owners[placed.path] = placed.download_id
            self.files.append(
                ShelfFile(
                    id=next(self.ids),
                    kind=placed.kind,
                    work_id=placed.work_id,
                    series=placed.series,
                    author=placed.author,
                    volume=placed.volume,
                    chapter=placed.chapter,
                    path=placed.path,
                    locked=False,
                    created_at=now,
                )
            )

    @override
    def set_work(self, file_ids: Sequence[int], work_id: str) -> None:
        self.files = [
            dataclasses.replace(f, work_id=work_id) if f.id in file_ids else f for f in self.files
        ]

    @override
    def read_link(self, series_id: str) -> SeriesLink | None:
        return self.links.get(series_id)

    @override
    def save_link(self, link: SeriesLink) -> None:
        self.links[link.series_id] = link

    @override
    def remove_link(self, series_id: str) -> bool:
        return self.links.pop(series_id, None) is not None

    @override
    def read_unlocked(self, since: int) -> list[ShelfFile]:
        return [f for f in self.files if not f.locked and f.created_at >= since]

    @override
    def read_files(self) -> list[ShelfFile]:
        return list(self.files)

    @override
    def mark_locked(self, file_ids: Sequence[int]) -> None:
        self.files = [
            ShelfFile(**{**f.__dict__, "locked": True}) if f.id in file_ids else f
            for f in self.files
        ]

    @override
    def read_shelved(self, work_id: str | None, series: str, kind: Kind) -> list[ShelfFile]:
        return [
            f
            for f in self.files
            if f.kind == kind and (f.work_id == work_id if work_id else f.series == series)
        ]

    @override
    def add_task(self, kind: TaskKind, path: str, data: bytes, now: int) -> None:
        task = LibraryTask(id=next(self.ids), kind=kind, path=path, data=data)
        self.tasks[task.id] = (task, "pending")

    @override
    def read_tasks(self) -> list[LibraryTask]:
        return [task for task, state in self.tasks.values() if state == "pending"]

    @override
    def mark_task(self, task_id: int, state: str, now: int) -> None:
        self.tasks[task_id] = (self.tasks[task_id][0], state)

    @override
    def remove_files(self, paths: Sequence[str]) -> None:
        self.files = [f for f in self.files if f.path not in paths]

    @override
    def read_download_files(self, download_id: int) -> list[ShelfFile]:
        return [f for f in self.files if self.owners.get(f.path) == download_id]

    @override
    def read_shelf_paths(self) -> set[str]:
        return {f.path for f in self.files}

    @override
    def find_shelved(self, text: str, limit: int) -> list[ShelfFile]:
        return [f for f in reversed(self.files) if text.lower() in f.path.lower()][:limit]

    @override
    def read_shelf_file(self, file_id: int) -> ShelfFile | None:
        return next((f for f in self.files if f.id == file_id), None)

    @override
    def add_item(self, item: NewItem, now: int) -> int:
        item_id = next(self.ids)
        self.items[item_id] = PlaceItem(
            id=item_id,
            **{k: v for k, v in item.__dict__.items()},
            request=None,
            error=None,
            destination=None,
            created_at=now,
            updated_at=now,
        )
        return item_id

    def change(self, item_id: int, **values: object) -> None:
        self.items[item_id] = dataclasses.replace(self.items[item_id], **values)  # type: ignore[arg-type]  # the fields named by the fake

    @override
    def update_item(self, item_id: int, item: NewItem, now: int) -> None:
        values = {k: v for k, v in item.__dict__.items() if k not in ("origin", "download_id")}
        self.change(item_id, **values, updated_at=now)

    @override
    def set_item_shelf(
        self, item_id: int, existing: tuple[int, ...], loose: tuple[float, ...]
    ) -> None:
        self.change(item_id, existing=existing, loose=loose)

    @override
    def read_items(self, *, placed: bool) -> list[PlaceItem]:
        return [
            i for i in sorted(self.items.values(), key=lambda i: -i.id) if placed or i.state in OPEN
        ]

    @override
    def read_item(self, item_id: int) -> PlaceItem | None:
        return self.items.get(item_id)

    @override
    def count_open(self) -> int:
        return sum(1 for i in self.items.values() if i.state in OPEN)

    @override
    def read_item_downloads(self) -> set[int]:
        return {i.download_id for i in self.items.values() if i.download_id is not None}

    @override
    def read_open_of(self, origin: ItemOrigin, *, ignored: bool = False) -> list[PlaceItem]:
        states = (*OPEN, "ignored") if ignored else OPEN
        return [i for i in self.items.values() if i.origin == origin and i.state in states]

    @override
    def count_open_of_download(self, download_id: int) -> int:
        return sum(
            1 for i in self.items.values() if i.download_id == download_id and i.state in OPEN
        )

    @override
    def delete_items(self, item_ids: Sequence[int]) -> None:
        for item_id in item_ids:
            del self.items[item_id]

    @override
    def ask(self, item_id: int, request: PlaceRequest, now: int) -> bool:
        item = self.items.get(item_id)
        if item is None or item.state not in OPEN or item.request is not None:
            return False
        self.change(item_id, request=request, error=None)
        return True

    @override
    def read_asked(self) -> list[PlaceItem]:
        return [i for i in self.items.values() if i.request is not None and i.state in OPEN]

    @override
    def mark_item_placed(self, item_id: int, destination: str, now: int) -> None:
        self.change(item_id, state="placed", request=None, error=None, destination=destination)

    @override
    def mark_item_ignored(self, item_id: int, now: int) -> None:
        self.change(item_id, state="ignored", request=None, error=None)

    @override
    def resume(self, item_id: int, state: ItemState, now: int) -> bool:
        item = self.items.get(item_id)
        if item is None or item.state != "ignored":
            return False
        self.change(item_id, state=state, request=None, error=None)
        return True

    @override
    def read_items_of_download(self, download_id: int) -> list[PlaceItem]:
        return [i for i in self.items.values() if i.download_id == download_id]

    @override
    def mark_item_failed(self, item_id: int, error: str, now: int) -> None:
        self.change(item_id, request=None, error=error)

    @override
    def mark_item_kept(
        self, item_id: int, files: Sequence[str], chapters: Sequence[float], now: int
    ) -> None:
        self.change(item_id, request=None, error=None, files=tuple(files), chapters=tuple(chapters))

    @override
    def record_scan(self, now: int) -> None:
        self.scans.append(now)

    @override
    def last_scan(self) -> int | None:
        return max(self.scans, default=None)

    @override
    def has_pending_scan(self) -> bool:
        return any(t.kind == "scan" and s == "pending" for t, s in self.tasks.values())

    @override
    def commit(self) -> None:
        pass

    @override
    def close(self) -> None:
        pass


class FakeTools(AudioTools):
    """ffmpeg played: each track lasts `seconds`, a merge writes the tracks joined, or fails."""

    def __init__(self, *, fails: bool = False, embedded: bytes | None = None) -> None:
        self.fails = fails
        self.embedded = embedded
        self.merged: list[tuple[list[str], str, Path | None, Path]] = []

    @override
    async def duration(self, track: Path) -> float:
        return 60.0

    @override
    async def embedded_cover(self, track: Path, out: Path) -> bool:
        if self.embedded is None:
            return False
        await anyio.Path(out).write_bytes(self.embedded)
        return True

    @override
    async def merge(
        self,
        tracks: Sequence[Path],
        title: str,
        cover: Path | None,
        out: Path,
        on_progress: Callable[[int], None],
    ) -> float:
        if self.fails:
            raise AudioError("exit 1")
        on_progress(50)
        await anyio.Path(out).write_bytes(
            b"".join([await anyio.Path(t).read_bytes() for t in tracks])
        )
        self.merged.append(([t.name for t in tracks], title, cover, out))
        return 60.0 * len(tracks)


class FakeCovers:
    def __init__(self, covers: dict[str, bytes] | None = None) -> None:
        self.covers = covers or {}

    async def cover(self, work_id: str) -> bytes | None:
        return self.covers.get(work_id)


@dataclass
class FakePlacementSettings:
    roots: dict[Kind, str]
    merge: bool = True
    covers_on: bool = True
    lock_on: bool = True
    scan_at: tuple[int, int] = (4, 30)
    uploads_at: str = "/nowhere/envois"
    keep_days: int = 7

    async def jellyfin(self) -> tuple[str | None, str | None]:
        return JELLYFIN_URL, JELLYFIN_KEY

    async def libraries(self) -> dict[Kind, str]:
        return dict(self.roots)

    async def merge_mp3(self) -> bool:
        return self.merge

    async def covers(self) -> bool:
        return self.covers_on

    async def lock_jellyfin(self) -> bool:
        return self.lock_on

    async def scan_time(self) -> tuple[int, int]:
        return self.scan_at

    async def uploads_folder(self) -> str:
        return self.uploads_at

    async def upload_keep_days(self) -> int:
        return self.keep_days


def libraries_of(roots: dict[Kind, str]) -> list[dict[str, object]]:
    """The libraries of Jellyfin of the shelf of a test: `/files/<name of the folder>`."""
    names = {"manga": "BD & Mangas", "ebook": "Livres", "audiobook": "Livres audio"}
    return [
        {
            "Name": names[kind],
            "CollectionType": "books",
            "ItemId": f"lib-{kind}",
            "Locations": [f"/files/{Path(root).name}"],
        }
        for kind, root in roots.items()
    ]


@dataclass
class Bench:
    service: PlacementService
    shelf: FakePlacementRepository
    downloads: FakeDownloadRepository
    qui: FakeQui
    jellyfin: FakeJellyfin
    journal: FakeJournal
    tools: FakeTools
    clock: FixedClock
    roots: dict[Kind, Path]
    hand: HandPlacement
    uploads: FakeUploadRepository
    store: UploadStore


def new_bench(
    tmp_path: Path,
    *,
    tools: FakeTools | None = None,
    covers: FakeCovers | None = None,
    merge: bool = True,
) -> Bench:
    roots: dict[Kind, Path] = {
        "manga": tmp_path / "files" / "comics",
        "ebook": tmp_path / "files" / "ebooks",
        "audiobook": tmp_path / "files" / "audiobooks",
    }
    for root in roots.values():
        root.mkdir(parents=True)
    settings = FakePlacementSettings(
        {k: str(v) for k, v in roots.items()},
        merge=merge,
        uploads_at=str(tmp_path / "files" / "envois"),
    )
    shelf = FakePlacementRepository()
    downloads = FakeDownloadRepository()
    qui = FakeQui()
    jellyfin = FakeJellyfin(
        libraries=libraries_of(settings.roots),
        items={f"lib-{k}": {"Id": f"lib-{k}", "Type": "CollectionFolder"} for k in roots},
    )
    journal = FakeJournal()
    clock = FixedClock()
    tools = tools or FakeTools()
    covers = covers or FakeCovers()
    service = PlacementService(
        lambda: shelf,
        lambda: downloads,
        torrent_clients(qui),
        JellyfinClient(httpx.AsyncClient(transport=httpx.MockTransport(jellyfin)), "0.5.0"),
        settings,
        tools,
        covers,
        journal,
        clock,
        PlacementOptions(every_seconds=0),
        DownloadCovers(covers, clock, 30),
    )
    uploads = FakeUploadRepository()
    store = UploadStore(tmp_path / "data" / "uploads")
    hand = HandPlacement(service, settings, lambda: uploads, store)
    return Bench(
        service, shelf, downloads, qui, jellyfin, journal, tools, clock, roots, hand, uploads, store
    )


def completed(
    bench: Bench,
    content: Path,
    *,
    kind: Kind = "manga",
    series: str = "Berserk",
    author: str = "Kentaro Miura",
    title: str = "Berserk.T41-T42.FRENCH.CBZ",
    volumes: Volumes | None = None,
    work_id: str | None = "mangaupdates:1",
) -> Download:
    """A download complete in qBittorrent, its torrent at `content`."""
    download = bench.downloads.add(
        NewDownload(
            release_id="0123456789abcdef",
            guid="g",
            title=title,
            indexer_id=1,
            indexer="Nyaa.si",
            size=1000,
            download_url="http://prowlarr.test/1/download?link=x",
            work_id=work_id,
            work_name=series,
            author=author,
            series=series,
            volumes=volumes or Volumes(kind="range", first=41, last=42),
            kind=kind,
            mode="auto",
            category=kind,
            created_at=0,
            created_by="sylvain",
        )
    )
    digest = f"{download.id:040x}"
    bench.downloads.change(download.id, stage="completed", info_hash=digest)
    bench.qui.torrents[digest] = {
        "hash": digest,
        "name": content.name,
        "state": "stalledUP",
        "progress": 1.0,
        "content_path": str(content),
    }
    found = bench.downloads.read(download.id)
    assert found is not None
    return found
