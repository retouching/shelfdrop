"""shelfdrop.modules.trackers.router: the trackers with their categories, and a category a
tracker does not know refused."""

import pytest

from shelfdrop.auth.types import Account
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.modules.trackers.router import read_trackers, refresh_trackers, save_trackers
from shelfdrop.modules.trackers.schemas import KindCategories, TrackerChoice, TrackersUpdate
from shelfdrop.releases.service import ReleaseService
from tests.unit.releases.support import FakeReleaseRepository, new_board, new_prowlarr
from tests.unit.settings.support import FakeSettingsReader
from tests.unit.works.support import FixedClock

ACCOUNT = Account(username="sylvain", user_id="u1")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_service() -> ReleaseService:
    repository = FakeReleaseRepository()
    client, _ = new_prowlarr()
    clock = FixedClock()
    board = new_board(client, repository, clock=clock)
    return ReleaseService(repository, board, client, board.options, clock, FakeSettingsReader())


@pytest.mark.anyio
async def test_a_tracker_shows_its_categories_and_the_default_ones_until_chosen() -> None:
    service = new_service()
    await refresh_trackers(service)

    read = await read_trackers(service)

    nyaa = next(t for t in read.trackers if t.name == "Nyaa.si")
    assert nyaa.default_categories is True
    assert nyaa.categories == KindCategories(manga=[7030], ebook=[7020], audiobook=[3030])
    assert {c.id: c.name for c in nyaa.available_categories}[156719] == (
        "Literature - English-translated"
    )

    saved = await save_trackers(
        service,
        ACCOUNT,
        TrackersUpdate(
            trackers=[
                TrackerChoice(
                    indexer_id=1,
                    used=True,
                    auto=True,
                    categories=KindCategories(manga=[100920, 100920, 7030], ebook=[], audiobook=[]),
                )
            ]
        ),
    )

    first = saved.trackers[0]
    assert (first.name, first.default_categories) == ("Nyaa.si", False)
    assert first.categories == KindCategories(manga=[100920, 7030], ebook=[], audiobook=[])


@pytest.mark.anyio
async def test_a_category_a_tracker_does_not_know_is_a_422() -> None:
    service = new_service()
    await refresh_trackers(service)
    unknown = KindCategories(manga=[100920], ebook=[7020], audiobook=[3030])

    with pytest.raises(ApiError) as refused:
        await save_trackers(
            service,
            ACCOUNT,
            TrackersUpdate(
                trackers=[TrackerChoice(indexer_id=4, used=True, auto=True, categories=unknown)]
            ),
        )

    assert (refused.value.status_code, refused.value.code) == (422, "unknown_tracker_category")
    assert refused.value.data == {"indexer_ids": [4]}
