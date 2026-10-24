"""WorkService: the recorded searches of real titles, replayed without network."""

from typing import override

import anyio
import httpx
import pytest

from shelfdrop.works.clients.myanimelist import MyAnimeListClient
from shelfdrop.works.exceptions import (
    MergeNotFoundError,
    MergeRefusedError,
    NoSourceAnsweredError,
    QueryTooShortError,
    SourceError,
    WorkNotFoundError,
)
from shelfdrop.works.flights import SearchFlights, SourceHealth
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
async def test_a_work_keeps_the_cover_and_the_summary_of_each_source() -> None:
    """The proposals of the page Jellyfin: every source that serves a cover or a summary."""
    case = next(c for c in CASES if c.slug == "berserk")
    result, _ = await run_search(case)
    berserk = result.works[0]

    assert {"mangaupdates", "kitsu"} <= set(berserk.covers)
    assert berserk.summaries["kitsu"].startswith("His name is Guts, the Black Swordsman")
    assert berserk.summaries["mangaupdates"].startswith("From Dark Horse:\nHis name is Guts")
    assert all("<" not in text for text in berserk.summaries.values())


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
    third = await service.search("Akira", "manga")
    clock.at += SearchOptions().source_rest_seconds + 1
    await service.search("Pluto", "manga")

    # Asked twice: one failure alone does not leave it out; the second one makes it rest.
    assert (first.unavailable, second.unavailable, third.unavailable) == (
        ("mangadex",),
        ("mangadex",),
        ("mangadex",),
    )
    assert down.searches == 3


@pytest.mark.anyio
async def test_a_retry_asks_a_resting_source_and_an_answer_clears_its_failures() -> None:
    down = CountingClient("mangadex", fails=True)
    service = new_service(
        WorkSources(clients=(CountingClient("kitsu"), down)),
        repository=FakeWorkRepository(),
        clock=FixedClock(),
    )
    await service.search("Berserk", "manga")
    await service.search("Monster", "manga")

    await service.search("Akira", "manga", retry=True)

    assert down.searches == 3
    health = SourceHealth()
    health.failed("bnf", 100.0, 2)
    health.answered("bnf")
    health.failed("bnf", 100.0, 2)
    assert not health.is_down("bnf", 50.0)


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


@pytest.mark.anyio
async def test_myanimelist_is_asked_once_its_client_id_is_saved_without_a_restart() -> None:
    """The Client ID is read from the settings at each search: saved on the page, the next
    search asks MyAnimeList, with it, on the same service."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    settings = FakeSettingsReader()
    http = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    service = new_service(
        WorkSources(clients=(MyAnimeListClient(http, settings.myanimelist_client_id),)),
        settings=settings,
    )

    await service.search("Berserk", "manga")
    assert seen == []
    settings.secrets["sources.myanimelist.client_id"] = "client-id-2"
    await service.search("Berserk", "manga")

    [request] = seen
    assert request.url.host == "api.myanimelist.net"
    assert request.headers["X-MAL-CLIENT-ID"] == "client-id-2"


class TwoWorks(CountingClient):
    """A source that answers two works to every search."""

    families: frozenset[Family] = frozenset({"manga", "book"})

    @override
    async def search(self, query: str, family: Family) -> list[Candidate]:
        self.searches += 1
        return [
            Candidate(source=self.name, source_id="1", title=f"{query} One"),
            Candidate(source=self.name, source_id="2", title=f"{query} Two"),
        ]


@pytest.mark.anyio
async def test_works_merged_by_hand_stay_merged_in_the_next_searches_then_split() -> None:
    repository = FakeWorkRepository()
    service = new_service(WorkSources(clients=(TwoWorks("kitsu"),)), repository=repository)
    found = await service.search("Berserk", "manga")
    assert len(found.works) == 2

    merged = await service.merge_works(
        "manga", [found.works[0].id, found.works[1].id], " Berserk  Tout "
    )
    again = await service.search("Berserk", "manga")
    read = await service.read_work(again.works[0].id)
    books = await service.search("Berserk", "ebook")

    [work] = again.works
    assert (work.merge_id, work.shelf_name) == (merged.id, "Berserk Tout")
    assert [p.id for p in work.parts] == ["kitsu:1", "kitsu:2"]
    assert read.merge_id == merged.id
    assert len(books.works) == 2
    await service.split_works(merged.id)
    assert len((await service.search("Berserk", "manga")).works) == 2
    with pytest.raises(MergeNotFoundError):
        await service.split_works(merged.id)


@pytest.mark.anyio
async def test_a_work_added_to_a_merge_replaces_it() -> None:
    class ThreeWorks(TwoWorks):
        @override
        async def search(self, query: str, family: Family) -> list[Candidate]:
            return [
                *await super().search(query, family),
                Candidate(source=self.name, source_id="3", title=f"{query} Three"),
            ]

    repository = FakeWorkRepository()
    service = new_service(WorkSources(clients=(ThreeWorks("kitsu"),)), repository=repository)
    found = await service.search("Berserk", "manga")
    first = await service.merge_works("manga", [w.id for w in found.works[:2]], "Berserk")
    pair = (await service.search("Berserk", "manga")).works
    merged = next(w for w in pair if w.merge_id == first.id)
    other = next(w for w in pair if w.merge_id is None)

    second = await service.merge_works("manga", [merged.id, other.id], "Berserk")

    assert list(repository.merges) == [second.id]
    assert set(second.keys) == {"kitsu:1", "kitsu:2", "kitsu:3"}
    [work] = (await service.search("Berserk", "manga")).works
    assert len(work.parts) == 3


@pytest.mark.anyio
@pytest.mark.parametrize(("ids", "name"), [(["kitsu:1", "kitsu:1"], "Berserk"), (["a", "b"], " ")])
async def test_a_merge_needs_two_works_and_a_name(ids: list[str], name: str) -> None:
    service = new_service(WorkSources(clients=(TwoWorks("kitsu"),)))
    with pytest.raises(MergeRefusedError):
        await service.merge_works("manga", ids, name)


@pytest.mark.anyio
async def test_a_merge_of_a_work_never_found_is_refused() -> None:
    service = new_service(WorkSources(clients=(TwoWorks("kitsu"),)))
    await service.search("Berserk", "manga")
    with pytest.raises(WorkNotFoundError):
        await service.merge_works("manga", ["kitsu:1", "kitsu:404"], "Berserk")
