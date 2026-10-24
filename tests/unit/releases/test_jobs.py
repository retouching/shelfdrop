"""shelfdrop.releases.jobs: the shared searches, the queue, the cache and the progress."""

import asyncio
from collections.abc import Callable, Sequence

import anyio
import pytest

from shelfdrop.releases.exceptions import ProwlarrError, SearchNotFoundError
from shelfdrop.releases.jobs import NameQuery, SearchBoard, SearchJob, name_state
from shelfdrop.releases.types import (
    FoundRelease,
    NameState,
    ReleaseOptions,
    SearchProgress,
    TrackerGroup,
)
from tests.unit.releases.support import FakeReleaseRepository, new_board, new_prowlarr
from tests.unit.works.support import FixedClock


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class GatedSource:
    """Prowlarr whose answers wait for the test to open their gate; it counts the requests."""

    def __init__(self, *, fails: bool = False) -> None:
        self.asked: list[str] = []
        self.requests: list[tuple[str, tuple[int, ...], tuple[int, ...]]] = []
        self.gates: dict[str, asyncio.Event] = {}
        self.fails = fails

    def gate(self, query: str) -> asyncio.Event:
        return self.gates.setdefault(query, asyncio.Event())

    async def search(
        self, query: str, categories: Sequence[int], indexer_ids: Sequence[int]
    ) -> list[FoundRelease]:
        self.asked.append(query)
        self.requests.append((query, tuple(categories), tuple(indexer_ids)))
        await self.gate(query).wait()
        if self.fails:
            raise ProwlarrError("HTTP 503")
        return [
            FoundRelease(
                guid=f"{query}|{indexer_id}",
                title=f"{query} T01",
                indexer_id=indexer_id,
                indexer="i",
                size=1,
                seeders=1,
            )
            for indexer_id in indexer_ids[:1]
        ]


MANGA = TrackerGroup(categories=(7030,), indexer_ids=(1, 2))


def start(board: SearchBoard, *names: str, refresh: bool = False) -> SearchJob:
    return board.start(
        mode="work",
        kind="manga",
        title=names[0],
        names=names,
        groups=[MANGA],
        refresh=refresh,
    )


async def finished(job: SearchJob) -> None:
    with anyio.fail_after(2):
        while job.finished_at is None:
            await job.changed.wait()


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


async def until(job: SearchJob, condition: Callable[[], bool]) -> None:
    """Wait on the changes of `job` until `condition` holds: a request reads the cache in the
    threadpool first, so how many turns of the loop it takes is not known."""
    with anyio.fail_after(2):
        while not condition():
            await job.changed.wait()


@pytest.mark.anyio
async def test_the_same_search_twice_is_one_search_and_one_request_per_name() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository())

    first = start(board, "Chainsaw Man", "Chensoo Man")
    second = start(board, "chainsaw.man", "Chensoo Man")
    await settle()
    source.gate("Chainsaw Man").set()
    source.gate("Chensoo Man").set()
    await finished(first)

    assert second is first
    assert board.progress(first).followers == 2
    assert sorted(source.asked) == ["Chainsaw Man", "Chensoo Man"]


@pytest.mark.anyio
async def test_two_searches_share_the_request_of_a_name_they_both_have() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository())

    one = start(board, "Chainsaw Man")
    other = start(board, "Chainsaw Man", "Chensoo Man")
    await settle()
    for gate in ("Chainsaw Man", "Chensoo Man"):
        source.gate(gate).set()
    await finished(other)

    assert one is not other
    assert source.asked.count("Chainsaw Man") == 1
    assert [n.found for n in board.progress(other).names] == [1, 1]


@pytest.mark.anyio
async def test_two_requests_at_most_and_the_others_wait_in_the_queue() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository())

    first = start(board, "Berserk", "Monster")
    second = start(board, "Pluto")
    # In the queue as soon as it starts, behind the names of the first one.
    assert board.progress(second).queued_ahead == 1
    await until(first, lambda: sorted(source.asked) == ["Berserk", "Monster"])

    assert board.progress(first).state == "running"
    assert board.progress(second).state == "queued"
    assert board.progress(second).queued_ahead == 1
    source.gate("Berserk").set()
    await until(second, lambda: "Pluto" in source.asked)
    assert source.asked[-1] == "Pluto"
    assert board.progress(second).state == "running"
    source.gate("Monster").set()
    source.gate("Pluto").set()
    await finished(second)
    await finished(first)


@pytest.mark.anyio
async def test_an_answer_is_kept_ten_minutes_unless_asked_again() -> None:
    source = GatedSource()
    for name in ("Berserk",):
        source.gate(name).set()
    repository = FakeReleaseRepository()
    clock = FixedClock()
    board = new_board(source, repository, clock=clock)

    await finished(start(board, "Berserk"))
    cached = start(board, "berserk")
    await finished(cached)
    assert len(source.asked) == 1
    assert board.progress(cached).fetched_at == clock.at

    await finished(start(board, "Berserk", refresh=True))
    assert len(source.asked) == 2
    clock.at += 600  # the release cache of the settings: 10 minutes
    await finished(start(board, "Berserk"))
    assert len(source.asked) == 3


@pytest.mark.anyio
async def test_a_request_that_takes_too_long_or_fails_is_failed() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository(), options=ReleaseOptions(timeout_seconds=0.05))

    job = start(board, "Berserk")
    await finished(job)

    progress = board.progress(job)
    assert [n.state for n in progress.names] == ["failed"]
    assert progress.state == "failed"

    down = GatedSource(fails=True)
    down.gate("Monster").set()
    board = new_board(down, FakeReleaseRepository())
    job = start(board, "Monster")
    await finished(job)
    assert board.progress(job).state == "failed"


@pytest.mark.anyio
async def test_one_name_failed_is_not_a_failed_search() -> None:
    source = GatedSource()
    source.gate("Berserk").set()
    board = new_board(source, FakeReleaseRepository(), options=ReleaseOptions(timeout_seconds=0.05))

    job = start(board, "Berserk", "Monster")
    await finished(job)

    assert board.progress(job).state == "done"
    assert [n.state for n in board.progress(job).names] == ["done", "failed"]


@pytest.mark.anyio
async def test_the_progress_comes_at_each_change_until_the_end() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository())
    job = start(board, "Berserk", "Monster")
    seen: list[SearchProgress] = []

    async def watch() -> None:
        async for progress in board.watch(job):
            seen.append(progress)

    def states() -> list[str]:
        return [n.state for n in board.progress(job).names]

    async with anyio.create_task_group() as group:
        group.start_soon(watch)
        await until(job, lambda: states() == ["running", "running"])
        source.gate("Berserk").set()
        await until(job, lambda: states() == ["done", "running"])
        source.gate("Monster").set()

    assert seen[-1].state == "done"
    assert [n.state for n in seen[-1].names] == ["done", "done"]
    assert any([n.state for n in p.names] == ["done", "running"] for p in seen)


@pytest.mark.anyio
async def test_a_search_goes_to_its_end_and_is_forgotten_after_a_while() -> None:
    clock = FixedClock()
    client, _ = new_prowlarr()
    board = new_board(client, FakeReleaseRepository(), clock=clock)

    job = start(board, "Jujutsu Kaisen")
    await finished(job)
    assert board.get(job.id) is job
    assert len(board.answers(job)[0][1]) == 9

    clock.at += ReleaseOptions().keep_seconds + 1
    start(board, "Berserk")
    with pytest.raises(SearchNotFoundError):
        board.get(job.id)


@pytest.mark.anyio
async def test_no_tracker_asked_is_an_empty_search() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository())

    job = board.start(
        mode="manual",
        kind="manga",
        title="Berserk",
        names=["Berserk"],
        groups=[],
        refresh=False,
    )
    await finished(job)

    assert source.asked == []
    assert board.progress(job).state == "done"


@pytest.mark.anyio
async def test_each_group_of_trackers_is_one_request_per_name_and_the_answers_merge() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository())
    nyaa = TrackerGroup(categories=(100920, 156719), indexer_ids=(3,))

    job = board.start(
        mode="work",
        kind="manga",
        title="Berserk",
        names=["Berserk"],
        groups=[MANGA, nyaa],
        refresh=False,
    )
    await until(job, lambda: len(source.requests) == 2)
    source.gate("Berserk").set()
    await finished(job)

    assert sorted(source.requests) == [
        ("Berserk", (7030,), (1, 2)),
        ("Berserk", (100920, 156719), (3,)),
    ]
    progress = board.progress(job)
    assert [(n.name, n.state, n.found) for n in progress.names] == [("Berserk", "done", 2)]
    assert [[r.indexer_id for r in releases] for _, releases in board.answers(job)] == [[1, 3]]


@pytest.mark.anyio
async def test_a_name_runs_while_its_groups_run_and_fails_when_each_failed() -> None:
    source = GatedSource()
    board = new_board(source, FakeReleaseRepository(), options=ReleaseOptions(timeout_seconds=0.2))
    other = TrackerGroup(categories=(7020,), indexer_ids=(3,))
    job = board.start(
        mode="work",
        kind="manga",
        title="Monster",
        names=["Monster"],
        groups=[MANGA, other],
        refresh=False,
    )
    await until(job, lambda: [n.state for n in board.progress(job).names] == ["running"])

    await finished(job)

    # Neither answered in time: the name failed.
    assert [n.state for n in board.progress(job).names] == ["failed"]


@pytest.mark.anyio
async def test_other_groups_of_trackers_are_another_search() -> None:
    source = GatedSource()
    source.gate("Berserk").set()
    board = new_board(source, FakeReleaseRepository())

    first = start(board, "Berserk")
    other = board.start(
        mode="work",
        kind="manga",
        title="Berserk",
        names=["Berserk"],
        groups=[TrackerGroup(categories=(7030, 100920), indexer_ids=(1, 2))],
        refresh=False,
    )
    await finished(first)
    await finished(other)

    assert other is not first
    assert [r[1] for r in source.requests] == [(7030,), (7030, 100920)]


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        (("queued", "queued"), "queued"),
        (("queued", "running"), "running"),
        (("done", "queued"), "running"),
        (("done", "failed"), "done"),
        (("failed", "failed"), "failed"),
    ],
)
def test_the_state_of_a_name_comes_from_its_requests(
    states: tuple[NameState, ...], expected: NameState
) -> None:
    queries = [
        NameQuery(key=str(i), query="q", categories=(), indexer_ids=(), owner="o", state=state)
        for i, state in enumerate(states)
    ]
    assert name_state(queries) == expected
