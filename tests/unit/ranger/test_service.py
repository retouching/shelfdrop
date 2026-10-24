import dataclasses

import pytest

from shelfdrop.placement.types import (
    ChaptersRequest,
    IgnoreRequest,
    NewItem,
    PlacedFile,
    VolumeRange,
    VolumeRequest,
)
from shelfdrop.ranger.exceptions import (
    ItemBusyError,
    ItemNotFoundError,
    ItemNotIgnoredError,
    RequestRefusedError,
)
from shelfdrop.ranger.service import RangerService, open_state
from tests.unit.placement.support import FakePlacementRepository
from tests.unit.works.support import FixedClock

VOLUME = VolumeRequest(kind="manga", work_id=None, series="Berserk", author="", volume=1)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_item(state: str = "unlinked") -> NewItem:
    return NewItem(
        origin="download",
        download_id=1,
        kind="manga",
        name="Berserk T01.cbz",
        path="/data/torrents/Berserk T01.cbz",
        files=("/data/torrents/Berserk T01.cbz",),
        size=1,
        state="chapters" if state == "chapters" else "unlinked",
        reason="no_volume",
    )


def chapters(*ranges: tuple[int, float, float]) -> ChaptersRequest:
    return ChaptersRequest(
        work_id=None,
        series="Chainsaw Man",
        author="",
        volumes=tuple(VolumeRange(volume=v, first=f, last=last) for v, f, last in ranges),
    )


@pytest.mark.anyio
async def test_a_request_goes_to_the_worker_once() -> None:
    shelf = FakePlacementRepository()
    service = RangerService(lambda: shelf, FixedClock())
    item_id = shelf.add_item(new_item(), 0)

    asked = await service.link(item_id, VOLUME)

    assert asked.request == VOLUME
    assert await service.count() == 1
    with pytest.raises(ItemBusyError):
        await service.link(item_id, VOLUME)
    with pytest.raises(ItemNotFoundError):
        await service.link(99, VOLUME)


@pytest.mark.anyio
async def test_volumes_of_chapters_must_fit_a_release_in_chapters() -> None:
    shelf = FakePlacementRepository()
    service = RangerService(lambda: shelf, FixedClock())
    single = shelf.add_item(new_item(), 0)
    release = shelf.add_item(new_item("chapters"), 0)

    for item_id, request in (
        (single, chapters((1, 1, 8))),
        (release, VOLUME),
        (release, chapters((1, 1, 8), (2, 8, 12))),
        (release, chapters((1, 1, 8), (1, 9, 12))),
        (release, chapters((1, 9, 8))),
        (release, chapters()),
    ):
        with pytest.raises(RequestRefusedError):
            await service.link(item_id, request)
    assert (await service.link(release, chapters((1, 1, 8), (2, 9, 12)))).request is not None


@pytest.mark.anyio
async def test_a_file_of_the_shelf_searched_is_corrected_by_a_file_of_ranger() -> None:
    shelf = FakePlacementRepository()
    service = RangerService(lambda: shelf, FixedClock())
    shelf.add_files(
        [
            PlacedFile(
                download_id=None,
                kind="manga",
                work_id=None,
                series="Berserk",
                author="",
                volume=1,
                chapter=None,
                path="/data/files/comics/Berserk/Berserk - T01.cbz",
            )
        ],
        0,
    )

    listing = await service.read("berserk - t01")
    [shelved] = listing.shelved
    item = await service.relink(shelved.id, VOLUME)

    assert (item.origin, item.files, item.request) == ("library", (shelved.path,), VOLUME)
    with pytest.raises(ItemNotFoundError):
        await service.relink(99, VOLUME)
    await service.scan()
    await service.scan()
    assert [t.kind for t in shelf.read_tasks()] == ["scan"]


@pytest.mark.anyio
async def test_a_file_is_ignored_by_the_worker_then_taken_back() -> None:
    shelf = FakePlacementRepository()
    service = RangerService(lambda: shelf, FixedClock())
    item_id = shelf.add_item(new_item("chapters"), 0)

    asked = await service.link(item_id, IgnoreRequest())
    assert asked.request == IgnoreRequest()
    with pytest.raises(ItemNotIgnoredError):
        await service.resume(item_id)
    shelf.mark_item_ignored(item_id, 0)
    assert await service.count() == 0

    # Taken back with its chapters: a release in chapters again.
    shelf.change(item_id, chapters=(1.0, 2.0))
    resumed = await service.resume(item_id)

    assert (resumed.state, resumed.request) == ("chapters", None)
    assert await service.count() == 1
    with pytest.raises(ItemNotFoundError):
        await service.resume(99)


def test_an_ignored_file_takes_back_the_state_of_its_origin() -> None:
    shelf = FakePlacementRepository()
    download = shelf.add_item(new_item(), 0)
    library = shelf.add_item(
        dataclasses.replace(new_item(), origin="library", state="misplaced"), 0
    )

    assert open_state(shelf.items[download]) == "unlinked"
    assert open_state(shelf.items[library]) == "misplaced"
