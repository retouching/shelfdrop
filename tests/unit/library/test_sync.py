"""LibrarySync: the metadata of the files placed sent again to Jellyfin, for a series or for
every library, in the background, on the fake Jellyfin."""

import json

import httpx
import pytest

from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.library.exceptions import SeriesNotFoundError
from shelfdrop.library.service import LibraryReader
from shelfdrop.library.sync import LibrarySync, volumes_of
from shelfdrop.placement.types import PlacedFile
from shelfdrop.works.types import Kind
from tests.unit.clients.support import FakeJellyfin
from tests.unit.library.test_service import Settings, item, shelf
from tests.unit.placement.support import FakePlacementRepository
from tests.unit.works.support import FixedClock


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def placed(
    path: str, volume: int | None, *, series: str = "Berserk", kind: Kind = "manga"
) -> PlacedFile:
    return PlacedFile(
        download_id=None,
        kind=kind,
        work_id=None,
        series=series,
        author="Kentaro Miura, Studio Gaga",
        volume=volume,
        chapter=None,
        path=path,
    )


def sync_of(jellyfin: FakeJellyfin) -> tuple[LibrarySync, FakePlacementRepository]:
    repository = FakePlacementRepository()
    repository.add_files(
        [
            placed("/data/files/comics/Berserk/Berserk - T01.cbz", 1),
            placed("/data/files/comics/Berserk/Berserk - T02.cbz", 2),
            # Placed, then gone from Jellyfin.
            placed("/data/files/comics/Berserk/Berserk - T03.cbz", 3),
            placed(
                "/data/files/ebooks/Robin Hobb/Les Aventuriers de la mer/01 - Le Vaisseau/x.epub",
                1,
                series="Les Aventuriers de la mer",
                kind="ebook",
            ),
        ],
        0,
    )
    client = JellyfinClient(httpx.AsyncClient(transport=httpx.MockTransport(jellyfin)), "0.5.0")
    return LibrarySync(
        LibraryReader(client, Settings()), lambda: repository, FixedClock()
    ), repository


async def ended(sync: LibrarySync) -> None:
    assert sync.task is not None
    await sync.task


@pytest.mark.anyio
async def test_a_sync_of_a_series_overwrites_the_authors_locks_and_leaves_the_images() -> None:
    jellyfin = shelf()
    jellyfin.items["b2"]["People"] = [
        {"Name": "Miura", "Type": "Author"},
        {"Name": "X", "Type": "Translator"},
    ]
    sync, repository = sync_of(jellyfin)
    assert sync.state().stage == "idle"

    started = await sync.start("berserk")
    await ended(sync)

    assert (started.stage, started.series_id) == ("running", "berserk")
    state = sync.state()
    assert (state.stage, state.changed, state.unchanged, state.not_found) == ("done", 2, 0, 1)
    volume = jellyfin.items["b2"]
    assert (volume["Name"], volume["SeriesName"], volume["IndexNumber"]) == (
        "Berserk - T02",
        "Berserk",
        2,
    )
    assert volume["People"] == [
        {"Name": "Kentaro Miura", "Type": "Author", "Role": ""},
        {"Name": "Studio Gaga", "Type": "Author", "Role": ""},
        {"Name": "X", "Type": "Translator"},
    ]
    assert volume["LockedFields"] == ["Cast", "Name"]
    # No image sent, no other series touched; the administrator read once.
    assert not [r for r in jellyfin.requests if r.url.path.endswith("/Images/Primary")]
    assert "SeriesName" not in jellyfin.items["mer1b"]
    assert jellyfin.paths().count("/Users") == 1
    assert [f.locked for f in repository.files] == [True, True, False, False]
    # Its folder refreshed once, not each volume (F40).
    assert [
        (i, p["metadataRefreshMode"], p["replaceAllMetadata"]) for i, p in jellyfin.refreshed
    ] == [("berserk", "FullRefresh", "false")]


@pytest.mark.anyio
async def test_a_sync_of_every_library_counts_what_held_its_metadata_already() -> None:
    jellyfin = shelf()
    sync, _ = sync_of(jellyfin)

    await sync.start(None)
    await ended(sync)
    first = sync.state()
    await sync.start(None)
    await ended(sync)

    assert (first.changed, first.not_found) == (3, 1)
    assert jellyfin.items["mer1b"]["SeriesName"] == "Les Aventuriers de la mer"
    again = sync.state()
    assert (again.stage, again.changed, again.unchanged, again.series_id) == ("done", 0, 3, None)
    # The first sync refreshed each series it changed, once; the second, nothing.
    assert [item_id for item_id, _ in jellyfin.refreshed] == ["berserk", "mer"]
    posts = [
        r for r in jellyfin.requests if r.method == "POST" and not r.url.path.endswith("/Refresh")
    ]
    assert all("IndexNumber" in json.loads(r.content) for r in posts)


@pytest.mark.anyio
async def test_a_refresh_that_fails_after_a_sync_never_fails_it() -> None:
    jellyfin = shelf()
    jellyfin.refresh_fails = True
    sync, repository = sync_of(jellyfin)

    await sync.start("berserk")
    await ended(sync)

    assert (sync.state().stage, sync.state().changed) == ("done", 2)
    assert [f.locked for f in repository.files] == [True, True, False, False]


@pytest.mark.anyio
async def test_a_sync_running_is_not_started_twice_and_a_failure_ends_it() -> None:
    jellyfin = shelf()
    sync, _ = sync_of(jellyfin)

    first = await sync.start(None)
    second = await sync.start("berserk")
    assert second is first
    await ended(sync)

    jellyfin.items["b1"] = item(
        "b1", "Book", "/files/comics/Berserk/Berserk - T01.cbz", "lib-manga"
    )
    jellyfin.administrator = False
    await sync.start(None)
    await ended(sync)
    assert sync.state().stage == "failed"
    assert sync.state().ended_at is not None


@pytest.mark.anyio
async def test_a_sync_of_an_unknown_series_is_refused_and_close_stops_it() -> None:
    sync, _ = sync_of(shelf())

    with pytest.raises(SeriesNotFoundError):
        await sync.start("b1")
    assert sync.state().stage == "idle"
    await sync.start(None)
    await sync.close()
    assert sync.task is not None
    assert sync.task.done()


def test_the_volumes_of_a_file_are_those_of_its_work_on_the_shelf() -> None:
    repository = FakePlacementRepository()
    repository.add_files(
        [
            placed("/a/1.cbz", 1),
            placed("/a/3.cbz", 3),
            placed("/a/x.cbz", 2, series="Other"),
        ],
        0,
    )
    files = repository.read_files()
    assert volumes_of(files[0], files) == [1, 3]
