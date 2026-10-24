"""ReleaseService: the searches of releases through the replayed Prowlarr, the trackers and the
filters."""

import anyio
import httpx
import pytest

from shelfdrop.releases.exceptions import InvalidRuleError, ReleaseNotFoundError, TooManyNamesError
from shelfdrop.releases.service import DEFAULT_MINIMUM, ReleaseService
from shelfdrop.releases.types import FilterRule, Filters, ReleaseSearch, Torrent
from shelfdrop.works.exceptions import QueryTooShortError
from shelfdrop.works.types import Kind
from tests.unit.releases.support import (
    FakeReleaseRepository,
    ProwlarrReplay,
    new_board,
    new_prowlarr,
)
from tests.unit.settings.support import FakeSettingsReader
from tests.unit.support import torrent_file
from tests.unit.works.support import FixedClock

ENGLISH = FilterRule(name="Anglais", pattern="ENGLISH, 1r0n", regex=False, score=-50)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_service(
    repository: FakeReleaseRepository | None = None,
    settings: FakeSettingsReader | None = None,
) -> tuple[ReleaseService, FakeReleaseRepository, ProwlarrReplay]:
    repository = repository or FakeReleaseRepository()
    client, replay = new_prowlarr()
    clock = FixedClock()
    board = new_board(client, repository, clock=clock)
    service = ReleaseService(
        repository, board, client, board.options, clock, settings or FakeSettingsReader()
    )
    return service, repository, replay


async def search(
    service: ReleaseService, *names: str, kind: Kind = "manga", manual: bool = False
) -> ReleaseSearch:
    progress = await service.start(
        mode="manual" if manual else "work", kind=kind, title=names[0], names=names, refresh=False
    )
    job = service.board.get(progress.id)
    with anyio.fail_after(2):
        while job.finished_at is None:
            await job.changed.wait()
    return await service.read(progress.id)


@pytest.mark.anyio
async def test_a_work_is_searched_under_its_names_in_the_trackers_asked() -> None:
    service, repository, replay = new_service()

    found = await search(service, "Jujutsu Kaisen", "Sorcery Fight")

    assert sorted(replay.searched()) == ["Jujutsu Kaisen", "Sorcery Fight"]
    asked = next(r for r in replay.requests if r.url.path == "/api/v1/search")
    # Read from Prowlarr at the first search: the torrent indexers on in Prowlarr alone.
    assert sorted(asked.url.params.get_list("indexerIds")) == ["1", "2", "3", "4"]
    assert asked.url.params.get_list("categories") == ["7030"]
    assert [t.name for t in repository.trackers] == [
        "Nyaa.si",
        "The Old School",
        "Abnormal",
        "YggTorrent",
        "C411",
    ]
    titles = [(r.title, r.indexer, r.matched_name) for r in found.releases]
    # The pack first, then volume by volume; T01 found by both names and on two trackers
    # (same infohash) once; T25 without seeds gone.
    assert titles[0][0].startswith("Jujutsu Kaisen (01-26)")
    assert (
        "Jujutsu.Kaisen.T01.FRENCH.MANGA.CBZ.eBook-PapriKa+",
        "The Old School",
        "Jujutsu Kaisen",
    ) in titles
    assert sum("T01.FRENCH.MANGA" in t for t, _, _ in titles) == 1
    assert not any("T25" in t for t, _, _ in titles)
    assert ("Sorcery Fight v04 (2019) (Digital) (1r0n)", "Nyaa.si", "Sorcery Fight") in titles
    volumes = [(r.volumes.kind, r.volumes.first) for r in found.releases]
    assert volumes[:3] == [("range", 1), ("single", 0), ("single", 1)]
    assert found.minimum == DEFAULT_MINIMUM


@pytest.mark.anyio
async def test_dusk_maiden_sets_amnesia_aside_and_the_manual_search_does_not() -> None:
    service, _, _ = new_service()

    work = await search(service, "Dusk Maiden of Amnesia", "Tasogare Otome × Amnesia")
    manual = await search(service, "Tasogare Otome x Amnesia", manual=True)

    amnesia = next(r for r in work.releases if r.title.startswith("Amnesia"))
    assert amnesia.rejected == "relevance"
    assert all(r.rejected is None for r in work.releases if r is not amnesia)
    assert all(r.rejected is None for r in manual.releases)
    assert {r.title for r in manual.releases} == {
        "Tasogare.Otome.x.Amnesia.T01.FRENCH.CBZ.eBook-PapriKa+",
        "Amnesia.T01.FRENCH.CBZ.eBook-NOTAG",
    }


@pytest.mark.anyio
async def test_an_audiobook_is_searched_in_its_category() -> None:
    service, _, replay = new_service()

    found = await search(service, "Les aventuriers de la mer", kind="audiobook")

    request = next(r for r in replay.requests if r.url.path == "/api/v1/search")
    assert request.url.params.get_list("categories") == ["3030"]
    assert found.releases[0].title.endswith("Kuppit")


@pytest.mark.anyio
async def test_the_names_are_checked() -> None:
    service, _, _ = new_service()

    with pytest.raises(TooManyNamesError):
        await service.start(
            mode="work",
            kind="manga",
            title="x",
            names=[f"Name {i}" for i in range(7)],
            refresh=False,
        )
    with pytest.raises(TooManyNamesError):
        await service.start(
            mode="manual", kind="manga", title="x", names=["a b", "c d"], refresh=False
        )
    with pytest.raises(QueryTooShortError):
        await service.start(mode="manual", kind="manga", title="x", names=["!"], refresh=False)


@pytest.mark.anyio
async def test_the_number_of_names_comes_from_the_settings() -> None:
    service, _, _ = new_service(settings=FakeSettingsReader({"search.max_names": 2}))

    with pytest.raises(TooManyNamesError):
        await service.start(
            mode="work", kind="manga", title="x", names=["Aa a", "Bb b", "Cc c"], refresh=False
        )


@pytest.mark.anyio
async def test_a_tracker_not_asked_is_not_searched_and_the_order_ranks() -> None:
    service, repository, replay = new_service()
    await service.refresh_trackers()
    # C411 first, Nyaa not asked.
    await service.save_trackers([(4, True, False), (1, False, False)], "sylvain")

    found = await search(service, "Jujutsu Kaisen")

    request = next(r for r in replay.requests if r.url.path == "/api/v1/search")
    assert sorted(request.url.params.get_list("indexerIds")) == ["2", "3", "4"]
    t01 = [r for r in found.releases if r.volumes.first == 1 and r.volumes.kind == "single"]
    # Same score: C411 comes first now, whatever its seeds.
    assert t01[0].indexer == "C411"
    assert repository.trackers[0].name == "C411"
    assert repository.audit == [("sylvain", "trackers")]


@pytest.mark.anyio
async def test_the_filters_score_and_set_aside_at_each_read() -> None:
    service, _, _ = new_service()
    await service.save_filters(Filters(rules=(ENGLISH,), minimum=-10), "sylvain")

    found = await search(service, "Jujutsu Kaisen", "Sorcery Fight")

    english = [r for r in found.releases if r.score == -50]
    assert {r.title for r in english} == {
        "Jujutsu.Kaisen.T03.ENGLISH.CBZ-1r0n",
        "Sorcery Fight v04 (2019) (Digital) (1r0n)",
    }
    assert all(r.rejected == "score" for r in english)
    assert english[0].score_rules[0].name == "Anglais"

    await service.save_filters(Filters(rules=(ENGLISH,), minimum=-100), "sylvain")
    again = await service.read(found.progress.id)
    assert all(r.rejected is None for r in again.releases if r.score == -50)


@pytest.mark.anyio
async def test_filters_are_saved_and_an_invalid_rule_is_refused() -> None:
    service, repository, _ = new_service()
    assert await service.read_filters() == Filters(rules=(), minimum=DEFAULT_MINIMUM)

    broken = FilterRule(name="Cassée", pattern="(FRENCH", regex=True, score=5)
    with pytest.raises(InvalidRuleError) as refused:
        await service.save_filters(Filters(rules=(ENGLISH, broken), minimum=0), "sylvain")
    assert refused.value.positions == [1]
    assert repository.commits == 0

    await service.save_filters(Filters(rules=(ENGLISH,), minimum=-20), "sylvain")
    assert await service.read_filters() == Filters(rules=(ENGLISH,), minimum=-20)


@pytest.mark.anyio
async def test_a_read_of_prowlarr_again_keeps_the_choices() -> None:
    service, _, _ = new_service()
    await service.refresh_trackers()
    await service.save_trackers([(2, True, True), (1, False, False)], "sylvain")

    trackers = await service.refresh_trackers()

    assert [(t.name, t.used) for t in trackers][:2] == [
        ("The Old School", True),
        ("Nyaa.si", False),
    ]
    assert [t.name for t in trackers if not t.prowlarr_enabled] == ["YggTorrent"]
    assert "NZBgeek" not in {t.name for t in trackers}


@pytest.mark.anyio
async def test_an_automatic_download_takes_a_release_kept_from_a_tracker_allowed() -> None:
    service, _, _ = new_service()
    await service.save_filters(Filters(rules=(ENGLISH,), minimum=-10), "sylvain")

    found = await search(service, "Jujutsu Kaisen", "Sorcery Fight")

    # C411 is left out of the automatic downloads at the first read of the trackers.
    assert {r.indexer for r in found.releases if r.automatic} == {
        "Nyaa.si",
        "The Old School",
        "Abnormal",
    }
    assert any(r.indexer == "C411" for r in found.releases)
    assert not any(r.automatic for r in found.releases if r.rejected is not None)


@pytest.mark.anyio
async def test_the_torrent_of_a_release_is_asked_by_its_id_through_its_download_link() -> None:
    service, _, replay = new_service()
    data = torrent_file("Jujutsu Kaisen T00.cbz")
    replay.downloads["101"] = httpx.Response(200, content=data)
    found = await search(service, "Jujutsu Kaisen")
    t00 = next(r for r in found.releases if r.title.startswith("Jujutsu.Kaisen.T00"))

    assert await service.torrent(t00.id) == Torrent(file=data)
    with pytest.raises(ReleaseNotFoundError):
        await service.torrent("0" * 16)
