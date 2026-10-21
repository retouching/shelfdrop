"""What the tests of the placement share: the files of the shelf in memory, ffmpeg played by a
fake, the settings, the covers of the sources, and builders of CBZ files."""

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
from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.downloads.types import Download, NewDownload
from shelfdrop.placement.audio import AudioError, AudioTools
from shelfdrop.placement.repository import PlacementRepository
from shelfdrop.placement.service import PlacementService
from shelfdrop.placement.types import LibraryTask, PlacedFile, PlacementOptions, ShelfFile, TaskKind
from shelfdrop.releases.types import Volumes
from shelfdrop.works.types import Kind
from tests.unit.clients.support import API_KEY, FakeJellyfin, FakeQui
from tests.unit.downloads.support import URL, FakeDownloadRepository
from tests.unit.support import FakeJournal, no_session
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

    @override
    def add_files(self, files: Sequence[PlacedFile], now: int) -> None:
        for placed in files:
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
    def read_unlocked(self, since: int) -> list[ShelfFile]:
        return [f for f in self.files if not f.locked and f.created_at >= since]

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

    async def qbittorrent(self) -> tuple[str | None, str | None]:
        return URL, FakeQui.KEY

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
    settings = FakePlacementSettings({k: str(v) for k, v in roots.items()}, merge=merge)
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
    service = PlacementService(
        lambda: shelf,
        lambda: downloads,
        QBittorrentClient(httpx.AsyncClient(transport=httpx.MockTransport(qui))),
        JellyfinClient(httpx.AsyncClient(transport=httpx.MockTransport(jellyfin)), "0.5.0"),
        settings,
        tools,
        covers or FakeCovers(),
        journal,
        clock,
        PlacementOptions(every_seconds=0),
    )
    return Bench(service, shelf, downloads, qui, jellyfin, journal, tools, clock, roots)


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
