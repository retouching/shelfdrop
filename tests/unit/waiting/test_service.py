"""WaitingService: the searches kept waiting, searched at the interval, found, journaled, and
leaving the list once placed."""

import dataclasses
import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import override

import pytest

from shelfdrop.placement.types import PlacedFile
from shelfdrop.releases.types import Release, Volumes
from shelfdrop.waiting.exceptions import WaitingNotFoundError
from shelfdrop.waiting.repository import WaitingRepository
from shelfdrop.waiting.service import WaitingService
from shelfdrop.waiting.types import Waiting, WaitingState, WaitOrder, Wanted
from shelfdrop.works.types import Kind
from tests.unit.downloads.support import release
from tests.unit.placement.support import FakePlacementRepository
from tests.unit.support import FakeJournal, no_session
from tests.unit.works.support import FixedClock

HOUR = 3600


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeWaitingRepository(WaitingRepository):
    def __init__(self) -> None:
        super().__init__(no_session())
        self.rows: dict[int, Waiting] = {}
        self.done: dict[int, int] = {}
        self.ids = itertools.count(1)

    @override
    def read_active(self) -> list[Waiting]:
        return [w for i, w in sorted(self.rows.items(), reverse=True) if i not in self.done]

    @override
    def read(self, waiting_id: int) -> Waiting | None:
        return None if waiting_id in self.done else self.rows.get(waiting_id)

    @override
    def add(
        self,
        *,
        work_id: str | None,
        title: str,
        author: str,
        kind: Kind,
        names: Sequence[str],
        wanted: Wanted,
        now: int,
        created_by: str,
    ) -> Waiting:
        waiting = Waiting(
            id=next(self.ids),
            work_id=work_id,
            title=title,
            author=author,
            kind=kind,
            names=tuple(names),
            wanted=wanted,
            state="waiting",
            releases=0,
            attempts=0,
            created_at=now,
            created_by=created_by,
            searched_at=None,
        )
        self.rows[waiting.id] = waiting
        return waiting

    @override
    def mark_searched(self, waiting_id: int, state: WaitingState, releases: int, now: int) -> None:
        row = self.rows[waiting_id]
        self.rows[waiting_id] = dataclasses.replace(
            row, state=state, releases=releases, searched_at=now, attempts=row.attempts + 1
        )

    @override
    def advance(self, waiting_id: int, chapter_from: float) -> None:
        row = self.rows[waiting_id]
        wanted = dataclasses.replace(row.wanted, chapter_from=chapter_from)
        self.rows[waiting_id] = dataclasses.replace(row, wanted=wanted)

    @override
    def mark_done(self, waiting_id: int, now: int) -> None:
        self.done[waiting_id] = now

    @override
    def commit(self) -> None:
        pass

    @override
    def close(self) -> None:
        pass


@dataclass
class FakeSearcher:
    found: list[Release] = field(default_factory=list)
    asked: list[tuple[Kind, str, tuple[str, ...]]] = field(default_factory=list)

    async def releases(self, kind: Kind, title: str, names: Sequence[str]) -> list[Release]:
        self.asked.append((kind, title, tuple(names)))
        return self.found


@dataclass
class FakeLibrary:
    volumes: set[int] = field(default_factory=set)

    async def volumes_of(self, kind: Kind, name: str) -> set[int]:
        return self.volumes


@dataclass
class EveryHours:
    hours: int = 6

    async def waiting_seconds(self) -> int:
        return self.hours * HOUR


@dataclass
class Bench:
    service: WaitingService
    repository: FakeWaitingRepository
    shelf: FakePlacementRepository
    searcher: FakeSearcher
    journal: FakeJournal
    clock: FixedClock


def new_bench() -> Bench:
    repository = FakeWaitingRepository()
    shelf = FakePlacementRepository()
    searcher = FakeSearcher()
    journal = FakeJournal()
    clock = FixedClock()
    service = WaitingService(
        lambda: repository,
        lambda: shelf,
        searcher,
        FakeLibrary({1, 2}),
        EveryHours(),
        journal,
        clock,
    )
    return Bench(service, repository, shelf, searcher, journal, clock)


def order(*wanted: Wanted) -> WaitOrder:
    return WaitOrder(
        work_id="mangaupdates:1",
        title="Chainsaw Man",
        author="Tatsuki Fujimoto",
        kind="manga",
        names=("Chainsaw Man", "チェンソーマン"),
        wanted=wanted,
        created_by="sylvain",
    )


def volume(n: int) -> Wanted:
    return Wanted(target="volume", volume=n)


def placed(n: int | None, chapter: float | None = None) -> PlacedFile:
    return PlacedFile(
        download_id=None,
        kind="manga",
        work_id="mangaupdates:1",
        series="Chainsaw Man",
        author="Tatsuki Fujimoto",
        volume=n,
        chapter=chapter,
        path=f"/data/files/comics/Chainsaw Man/{n}-{chapter}.cbz",
    )


@pytest.mark.anyio
async def test_one_search_for_each_volume_and_never_twice() -> None:
    bench = new_bench()

    added, skipped = await bench.service.add(order(volume(23), volume(24)))
    again, skipped_again = await bench.service.add(order(volume(24), volume(25)))

    assert [v.waiting.wanted.volume for v in added] == [23, 24]
    assert skipped == 0
    assert [v.waiting.wanted.volume for v in again] == [25]
    assert skipped_again == 1
    # Never searched: due now.
    assert added[0].next_search_at == bench.clock.now()


@pytest.mark.anyio
async def test_a_round_searches_those_due_and_a_release_found_goes_to_the_journal() -> None:
    bench = new_bench()
    await bench.service.add(order(volume(23), Wanted(target="chapters", chapter_from=233)))
    bench.searcher.found = [
        dataclasses.replace(
            release("Chainsaw.Man.T23.FRENCH.CBZ"),
            volumes=Volumes(kind="single", first=23, last=23),
        ),
        dataclasses.replace(release("Chainsaw.Man.T23.Bad"), rejected="score"),
    ]

    assert await bench.service.round() == 2

    views = {v.waiting.wanted.target: v for v in await bench.service.read()}
    assert (views["volume"].waiting.state, views["volume"].waiting.releases) == ("found", 1)
    assert views["chapters"].waiting.state == "waiting"
    assert views["volume"].next_search_at == bench.clock.now() + 6 * HOUR
    assert bench.searcher.asked[0] == ("manga", "Chainsaw Man", ("Chainsaw Man", "チェンソーマン"))
    [event] = bench.journal.of("found")
    assert event.facts == {
        "work": "Chainsaw Man",
        "wanted": "volume",
        "volume": 23,
        "chapter_from": None,
        "chapter_to": None,
        "releases": 1,
    }
    # Not due before the interval; found again: no second message.
    assert await bench.service.round() == 0
    bench.clock.at += 6 * HOUR
    assert await bench.service.round() == 2
    assert len(bench.journal.of("found")) == 1


@pytest.mark.anyio
async def test_a_volume_placed_leaves_the_list_and_chapters_move_on() -> None:
    bench = new_bench()
    await bench.service.add(
        order(volume(23), volume(24), Wanted(target="chapters", chapter_from=233))
    )
    bench.shelf.add_files([placed(23), placed(None, 233), placed(None, 234)], 0)

    await bench.service.tidy()

    left = {v.waiting.wanted.target: v.waiting for v in await bench.service.read()}
    assert [
        v.waiting.wanted.volume for v in await bench.service.read() if v.waiting.wanted.volume
    ] == [24]
    assert left["chapters"].wanted.chapter_from == 235


@pytest.mark.anyio
async def test_a_search_now_a_removal_and_the_volumes_owned() -> None:
    bench = new_bench()
    [view], _ = await bench.service.add(order(volume(23)))
    bench.shelf.add_files([placed(3)], 0)

    searched = await bench.service.search(view.waiting.id)
    await bench.service.remove(view.waiting.id)

    assert searched.waiting.attempts == 1
    assert await bench.service.read() == []
    with pytest.raises(WaitingNotFoundError):
        await bench.service.search(view.waiting.id)
    assert await bench.service.owned("manga", "Chainsaw Man", "mangaupdates:1") == [1, 2, 3]
