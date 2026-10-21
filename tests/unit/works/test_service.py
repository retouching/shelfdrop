"""WorkService: the recorded searches of real titles, replayed without network."""

from typing import override

import anyio
import httpx
import pytest

from shelfdrop.works.exceptions import (
    NoSourceAnsweredError,
    QueryTooShortError,
    SourceError,
    WorkNotFoundError,
)
from shelfdrop.works.flights import SearchFlights
from shelfdrop.works.service import WorkSources
from shelfdrop.works.types import Candidate, Family, Name, SearchOptions, SourceName, WorkSearch
from tests.unit.settings.support import FakeSettingsReader
from tests.unit.works.cases import CASES, Case
from tests.unit.works.support import (
    FakeWorkRepository,
    FixedClock,
    ReplayTransport,
    load,
    new_service,
    replayed_service,
)


async def run_search(case: Case) -> tuple[WorkSearch, ReplayTransport]:
    transport = ReplayTransport(load(case.slug))
    async with httpx.AsyncClient(transport=transport) as http:
        result = await replayed_service(http).search(case.query, case.kind)
    return result, transport


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=[c.slug for c in CASES])
async def test_recorded_search(case: Case) -> None:
    result, transport = await run_search(case)
    assert not transport.missing, "a request was not recorded: run tests.unit.works.record"
    assert result.works, "no work found"
    first = result.works[0]
    assert first.shelf_name == case.shelf_name
    checked = {n.title for n in first.names if n.checked}
    for name in case.names:
        assert name in checked, f"{name!r} not searched; checked: {sorted(checked)}"
    if case.author:
        assert case.author in first.authors
    if case.volumes:
        assert first.volumes == case.volumes
    if case.volumes_fr:
        assert first.volumes_fr == case.volumes_fr
    assert first.shelf_name not in case.not_first
    shown = {n.title for n in first.names}
    for name in case.unchecked:
        assert name in shown, f"{name!r} not shown"
        assert name not in checked, f"{name!r} searched by default"


@pytest.mark.anyio
async def test_dusk_maiden_is_not_amnesia() -> None:
    """The 21/10 mistake: 'Amnesia' (1995) must stay a separate, lower work."""
    case = next(c for c in CASES if c.slug == "dusk-maiden")
    result, _ = await run_search(case)
    first = result.works[0]
    assert "Tasogare Otome × Amnesia" in {n.title for n in first.names}
    amnesia = [w for w in result.works if w.shelf_name == "Amnesia"]
    assert amnesia
    assert amnesia[0].id != first.id


@pytest.mark.anyio
async def test_down_sources_are_named() -> None:
    case = next(c for c in CASES if c.slug == "chainsaw-man")
    result, _ = await run_search(case)
    assert result.unavailable == ("anilist",)
    assert "mangaupdates" not in result.unavailable


@pytest.mark.anyio
async def test_manga_side_forms_are_apart() -> None:
    case = next(c for c in CASES if c.slug == "chainsaw-man")
    result, _ = await run_search(case)
    assert all(w.form not in ("novel", "doujinshi", "anthology") for w in result.works)
    assert any(w.form in ("novel", "doujinshi") for w in result.other_forms)


class CountingClient:
    """A source that answers one candidate, or fails, and counts its searches."""

    families: frozenset[Family] = frozenset({"manga"})

    def __init__(self, name: SourceName, *, fails: bool = False, delay: float = 0.0) -> None:
        self.name: SourceName = name
        self.fails = fails
        self.delay = delay
        self.searches = 0

    async def search(self, query: str, family: Family) -> list[Candidate]:
        self.searches += 1
        await anyio.sleep(self.delay)
        if self.fails:
            raise SourceError("HTTP 503")
        return [Candidate(source=self.name, source_id="1", title=query)]


@pytest.mark.anyio
async def test_a_second_search_reads_the_cache() -> None:
    client = CountingClient("kitsu")
    repository = FakeWorkRepository()
    service = new_service(WorkSources(clients=(client,)), repository=repository)

    await service.search("Berserk", "manga")
    again = await service.search("berserk ", "manga")

    assert client.searches == 1
    assert again.works[0].title == "Berserk"
    assert repository.commits == 2


@pytest.mark.anyio
async def test_a_failed_source_rests_then_is_asked_again() -> None:
    down = CountingClient("mangadex", fails=True)
    clock = FixedClock()
    service = new_service(
        WorkSources(clients=(CountingClient("kitsu"), down)),
        repository=FakeWorkRepository(),
        clock=clock,
    )

    first = await service.search("Berserk", "manga")
    second = await service.search("Monster", "manga")
    clock.at += SearchOptions().source_rest_seconds + 1
    await service.search("Pluto", "manga")

    assert first.unavailable == ("mangadex",)
    assert second.unavailable == ("mangadex",)
    assert down.searches == 2


@pytest.mark.anyio
async def test_two_identical_searches_share_one_run() -> None:
    client = CountingClient("kitsu", delay=0.05)
    flights = SearchFlights()
    service = new_service(WorkSources(clients=(client,)), flights=flights)
    results: list[WorkSearch] = []

    async def search() -> None:
        results.append(await service.search("Berserk", "manga"))

    async with anyio.create_task_group() as group:
        group.start_soon(search)
        group.start_soon(search)

    assert client.searches == 1
    assert results[0] == results[1]
    assert not flights.running


@pytest.mark.anyio
async def test_no_source_answered() -> None:
    service = new_service(WorkSources(clients=(CountingClient("kitsu", fails=True),)))

    with pytest.raises(NoSourceAnsweredError):
        await service.search("Berserk", "manga")


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["", " ", "a", "!!", "é"])
async def test_a_query_needs_two_letters(query: str) -> None:
    client = CountingClient("kitsu")
    service = new_service(WorkSources(clients=(client,)))

    with pytest.raises(QueryTooShortError):
        await service.search(query, "manga")
    assert client.searches == 0


@pytest.mark.anyio
async def test_a_work_found_is_read_by_its_id_until_it_expires() -> None:
    clock = FixedClock()
    service = new_service(
        WorkSources(clients=(CountingClient("kitsu"),)),
        repository=FakeWorkRepository(),
        clock=clock,
    )
    found = await service.search("Berserk", "manga")

    work = await service.read_work(found.works[0].id)
    clock.at += SearchOptions().work_seconds
    with pytest.raises(WorkNotFoundError):
        await service.read_work(work.id)


class BnfClient(CountingClient):
    """The BnF of the tests: it knows one French edition, 'Gunnm', and nothing else."""

    families: frozenset[Family] = frozenset({"manga", "book"})

    def __init__(self) -> None:
        super().__init__("bnf")
        self.asked: list[str] = []

    @override
    async def search(self, query: str, family: Family) -> list[Candidate]:
        self.asked.append(query)
        if query != "Gunnm":
            return []
        return [
            Candidate(
                source="bnf",
                source_id="ark:/gunnm",
                title="Gunnm",
                names=(Name(title="Gunnm", language="fr"),),
                authors=("Yukito Kishiro",),
                volumes_fr=9,
            )
        ]


class AlitaClient(CountingClient):
    @override
    async def search(self, query: str, family: Family) -> list[Candidate]:
        return [
            Candidate(
                source="kitsu",
                source_id="1",
                title="Battle Angel Alita",
                names=(
                    Name(title="Battle Angel Alita", language="en"),
                    Name(title="Gunnm", language="ja-ro"),
                ),
                authors=("Kishiro Yukito",),
                volumes=9,
            )
        ]


@pytest.mark.anyio
async def test_the_bnf_is_asked_again_under_the_names_of_the_work() -> None:
    bnf = BnfClient()
    repository = FakeWorkRepository()
    service = new_service(WorkSources(clients=(AlitaClient("kitsu"), bnf)), repository=repository)

    result = await service.search("Battle Angel Alita", "manga")

    assert bnf.asked == ["Battle Angel Alita", "Gunnm"]
    assert result.works[0].shelf_name == "Gunnm"
    assert result.works[0].volumes_fr == 9
    assert ("bnf", "manga|gunnm") in repository.answers


@pytest.mark.anyio
async def test_the_bnf_asked_again_reads_its_cache_too() -> None:
    bnf = BnfClient()
    service = new_service(
        WorkSources(clients=(AlitaClient("kitsu"), bnf)), repository=FakeWorkRepository()
    )
    await service.search("Battle Angel Alita", "manga")

    again = await service.search("Alita battle angel", "manga")

    assert bnf.asked == ["Battle Angel Alita", "Gunnm", "Alita battle angel"]
    assert again.works[0].volumes_fr == 9


@pytest.mark.anyio
async def test_a_down_bnf_is_not_asked_again() -> None:
    bnf = CountingClient("bnf", fails=True)
    service = new_service(WorkSources(clients=(AlitaClient("kitsu"), bnf)))

    result = await service.search("Battle Angel Alita", "manga")

    assert bnf.searches == 1
    assert result.unavailable == ("bnf",)
    assert result.works[0].shelf_name == "Battle Angel Alita"


@pytest.mark.anyio
async def test_a_source_switched_off_is_not_asked() -> None:
    off = CountingClient("mangadex")
    service = new_service(
        WorkSources(clients=(CountingClient("kitsu"), off)),
        settings=FakeSettingsReader({"sources.mangadex.enabled": False}),
    )

    result = await service.search("Berserk", "manga")

    assert off.searches == 0
    assert result.unavailable == ()


@pytest.mark.anyio
async def test_the_answers_are_kept_as_long_as_the_settings_say() -> None:
    client = CountingClient("kitsu")
    clock = FixedClock()
    service = new_service(
        WorkSources(clients=(client,)),
        clock=clock,
        settings=FakeSettingsReader({"search.work_cache_hours": 1}),
    )

    await service.search("Berserk", "manga")
    clock.at += 3599
    await service.search("Berserk", "manga")
    clock.at += 1
    await service.search("Berserk", "manga")

    assert client.searches == 2
