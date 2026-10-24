"""What the tests of the downloads share: the downloads in memory, Prowlarr giving torrents,
qBittorrent behind qui (`FakeQui`), and the releases of a search."""

import dataclasses
from collections.abc import Sequence
from typing import Final, override

import httpx

from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.downloads.covers import DownloadCovers
from shelfdrop.downloads.repository import DownloadRepository
from shelfdrop.downloads.sender import DownloadSender
from shelfdrop.downloads.service import DownloadService
from shelfdrop.downloads.types import Download, DownloadOptions, Failure, NewDownload
from shelfdrop.releases.exceptions import ProwlarrError, SearchNotFoundError
from shelfdrop.releases.results import release_id
from shelfdrop.releases.types import (
    Release,
    ReleaseSearch,
    SearchMode,
    SearchProgress,
    Torrent,
    Volumes,
)
from shelfdrop.works.types import Kind
from tests.unit.clients.support import FakeQui
from tests.unit.support import FakeJournal, no_session
from tests.unit.works.support import FixedClock

URL: Final = "http://qui.test:7476"
# Looks of a send, at once: the tests wait on nothing.
FAST: Final = DownloadOptions(check_seconds=0)


class FakeDownloadRepository(DownloadRepository):
    """The downloads in memory; one instance plays every session. It counts the commits."""

    def __init__(self) -> None:
        super().__init__(no_session())
        self.rows: dict[int, Download] = {}
        self.torrents: dict[int, Torrent] = {}
        self.commits = 0

    @override
    def add(self, new: NewDownload) -> Download:
        download = Download(
            id=len(self.rows) + 1,
            info_hash=None,
            release_id=new.release_id,
            title=new.title,
            indexer=new.indexer,
            size=new.size,
            download_url=new.download_url,
            work_id=new.work_id,
            work_name=new.work_name,
            author=new.author,
            series=new.series,
            volumes=new.volumes,
            kind=new.kind,
            mode=new.mode,
            category=new.category,
            stage="sending",
            failure=None,
            attempts=1,
            created_at=new.created_at,
            created_by=new.created_by,
            added_at=None,
        )
        self.rows[download.id] = download
        return download

    @override
    def read(self, download_id: int) -> Download | None:
        return self.rows.get(download_id)

    @override
    def read_recent(self, limit: int) -> list[Download]:
        return sorted(self.rows.values(), key=lambda d: (-d.created_at, -d.id))[:limit]

    @override
    def read_sending(self) -> list[int]:
        return [d.id for d in self.rows.values() if d.stage == "sending"]

    @override
    def read_torrent(self, download_id: int) -> Torrent | None:
        return self.torrents.get(download_id)

    @override
    def save_torrent(self, download_id: int, torrent: Torrent, info_hash: str) -> None:
        self.torrents[download_id] = torrent
        self.change(download_id, info_hash=info_hash)

    @override
    def mark_added(self, download_id: int, now: int) -> None:
        if self.rows[download_id].added_at is None:
            self.change(download_id, added_at=now)

    @override
    def mark_sent(self, download_id: int, now: int) -> None:
        self.change(download_id, stage="sent", failure=None)

    @override
    def mark_failed(self, download_id: int, failure: Failure) -> None:
        self.change(download_id, stage="failed", failure=failure)

    @override
    def mark_completed(self, download_ids: Sequence[int], now: int) -> list[int]:
        done = [i for i in download_ids if self.rows[i].stage == "sent"]
        for download_id in done:
            self.change(download_id, stage="completed")
        return done

    @override
    def read_sent(self) -> list[Download]:
        return [d for d in self.rows.values() if d.stage == "sent" and d.info_hash]

    @override
    def read_to_place(self) -> list[Download]:
        return [d for d in self.rows.values() if d.stage == "completed" and d.mode == "auto"]

    @override
    def read_left(self) -> list[Download]:
        return [
            d
            for d in self.rows.values()
            if d.stage == "unplaced" or (d.stage == "completed" and d.mode == "manual")
        ]

    @override
    def mark_placed(self, download_id: int, destination: str, now: int) -> None:
        self.change(download_id, stage="placed", destination=destination, placing_percent=None)

    @override
    def mark_unplaced(self, download_id: int, reason: str, now: int) -> None:
        self.change(download_id, stage="unplaced", unplaced=reason, placing_percent=None)

    @override
    def mark_placing(self, download_id: int, percent: int) -> None:
        self.change(download_id, placing_percent=percent)

    @override
    def mark_retried(self, download_id: int) -> None:
        row = self.rows[download_id]
        self.change(download_id, stage="sending", failure=None, attempts=row.attempts + 1)

    def change(self, download_id: int, **values: object) -> None:
        self.rows[download_id] = dataclasses.replace(self.rows[download_id], **values)  # type: ignore[arg-type]  # the fields named by the fake

    @override
    def commit(self) -> None:
        self.commits += 1

    @override
    def close(self) -> None:
        pass


class FakeProwlarr:
    """Prowlarr giving the torrent of each download link it knows; any other fails."""

    def __init__(self, torrents: dict[str, Torrent] | None = None) -> None:
        self.torrents = torrents or {}
        self.asked: list[str] = []

    async def torrent(self, link: str) -> Torrent:
        self.asked.append(link)
        found = self.torrents.get(link)
        if found is None:
            raise ProwlarrError("HTTP 410", status=410)
        return found


class FakeWorkCovers:
    """The covers of the works the search kept, by id; `broken`, each read fails."""

    def __init__(self) -> None:
        self.covers: dict[str, bytes] = {}
        self.asked: list[str] = []
        self.broken = False

    async def cover(self, work_id: str) -> bytes | None:
        self.asked.append(work_id)
        if self.broken:
            raise OSError("cache unreadable")
        return self.covers.get(work_id)


class FakeAddress:
    """The address of qui and the key of its client proxy, as the settings give them."""

    def __init__(self, url: str | None = URL, key: str | None = FakeQui.KEY) -> None:
        self.url = url
        self.key = key

    async def qbittorrent(self) -> tuple[str | None, str | None]:
        return self.url, self.key


class FakeFinder:
    """The searches kept, by id."""

    def __init__(self) -> None:
        self.searches: dict[str, ReleaseSearch] = {}

    async def read(self, search_id: str) -> ReleaseSearch:
        found = self.searches.get(search_id)
        if found is None:
            raise SearchNotFoundError
        return found


def release(title: str, *, indexer: str = "Nyaa.si", automatic: bool = True) -> Release:
    """A release of a search, its download link `http://prowlarr.test/1/download?link=<title>`."""
    guid = f"https://tracker.test/{title}"
    return Release(
        id=release_id(guid),
        guid=guid,
        title=title,
        matched_name=title,
        indexer_id=1,
        indexer=indexer,
        indexer_rank=0,
        info_url=None,
        info_hash=None,
        seeders=5,
        size=1000,
        volumes=Volumes(kind="single", first=1, last=1),
        score=0,
        score_rules=(),
        rejected=None,
        automatic=automatic,
        download_url=f"http://prowlarr.test/1/download?link={title}",
    )


def search_of(
    search_id: str,
    releases: Sequence[Release],
    *,
    mode: SearchMode = "work",
    kind: Kind = "manga",
    title: str = "Berserk",
) -> ReleaseSearch:
    return ReleaseSearch(
        progress=SearchProgress(
            id=search_id,
            mode=mode,
            kind=kind,
            title=title,
            state="done",
            names=(),
            queued_ahead=0,
            followers=1,
            fetched_at=None,
        ),
        releases=tuple(releases),
        minimum=-100,
    )


@dataclasses.dataclass
class Desk:
    """A service and its sender, on the same fakes."""

    service: DownloadService
    sender: DownloadSender
    repository: FakeDownloadRepository
    prowlarr: FakeProwlarr
    qui: FakeQui
    finder: FakeFinder
    clock: FixedClock
    journal: FakeJournal
    covers: FakeWorkCovers


def new_desk(
    *,
    qui: FakeQui | None = None,
    options: DownloadOptions = FAST,
    address: FakeAddress | None = None,
) -> Desk:
    repository = FakeDownloadRepository()
    prowlarr = FakeProwlarr()
    qui = qui or FakeQui()
    finder = FakeFinder()
    clock = FixedClock()
    qbittorrent = QBittorrentClient(httpx.AsyncClient(transport=httpx.MockTransport(qui)))
    address = address or FakeAddress()
    journal = FakeJournal()
    covers = FakeWorkCovers()
    download_covers = DownloadCovers(covers, clock, 30)
    sender = DownloadSender(
        prowlarr, qbittorrent, address, lambda: repository, options, clock, journal, download_covers
    )
    service = DownloadService(
        repository, sender, qbittorrent, address, finder, options, clock, journal, download_covers
    )
    return Desk(service, sender, repository, prowlarr, qui, finder, clock, journal, covers)
