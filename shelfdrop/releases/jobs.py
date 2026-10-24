"""The Prowlarr searches of every request, in memory (one process, one worker): a search is
shared by whoever asks the same one while it runs, each of its names is one Prowlarr request
per group of trackers (those that search the same categories of its kind), shared too, at
most `parallel` at a time and the next ones in a queue, and every answer is kept a while in
the cache. A search goes to its end even when nobody follows it any more.
One instance per process (a container singleton)."""

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import anyio
import anyio.to_thread

from shelfdrop.releases.exceptions import ProwlarrError, SearchNotFoundError
from shelfdrop.releases.guess import clean_query
from shelfdrop.releases.repository import RepositoryFactory
from shelfdrop.releases.types import (
    FoundRelease,
    NameProgress,
    NameState,
    ReleaseOptions,
    SearchMode,
    SearchProgress,
    SearchState,
    TrackerGroup,
)
from shelfdrop.utils.text import normalize
from shelfdrop.works.types import Clock, Kind

logger = logging.getLogger(__name__)


class ReleaseSource(Protocol):
    async def search(
        self, query: str, categories: Sequence[int], indexer_ids: Sequence[int]
    ) -> list[FoundRelease]: ...


class AnswerTime(Protocol):
    """How long an answer of Prowlarr is reused, read at each answer (the settings page)."""

    async def release_answer_seconds(self) -> int: ...


@dataclass(eq=False, kw_only=True)
class NameQuery:
    """One Prowlarr request: a name, the categories of a group of trackers, its indexers."""

    key: str
    query: str
    categories: tuple[int, ...]
    indexer_ids: tuple[int, ...]
    owner: str
    """The search that asked it first."""
    state: NameState = "queued"
    releases: tuple[FoundRelease, ...] = ()
    fetched_at: float | None = None
    jobs: list["SearchJob"] = field(default_factory=list)
    done: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass(eq=False, kw_only=True)
class SearchJob:
    id: str
    key: str
    mode: SearchMode
    kind: Kind
    title: str
    names: list[tuple[str, tuple[NameQuery, ...]]] = field(default_factory=list)
    """Each name, with its request to each group of trackers."""
    followers: int = 1
    finished_at: float | None = None
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    def notify(self) -> None:
        event, self.changed = self.changed, asyncio.Event()
        event.set()

    def queries(self) -> list[NameQuery]:
        return [q for _, queries in self.names for q in queries]


def name_state(queries: Sequence[NameQuery]) -> NameState:
    """The state of a name from those of its requests: done once each ended and one found,
    failed once each failed, queued while none started, running otherwise."""
    states = {q.state for q in queries}
    if states <= {"done", "failed"}:
        return "done" if "done" in states else "failed"
    return "queued" if states == {"queued"} else "running"


def query_key(query: str, categories: Sequence[int], indexer_ids: Sequence[int]) -> str:
    """'Chainsaw Man' and 'chainsaw.man' give the same key."""
    cats = ",".join(map(str, categories))
    ids = ",".join(map(str, indexer_ids))
    return f"{normalize(query)}|{cats}|{ids}"


class SearchBoard:
    def __init__(
        self,
        source: ReleaseSource,
        repositories: RepositoryFactory,
        options: ReleaseOptions,
        clock: Clock,
        answer_time: AnswerTime,
    ) -> None:
        self.source = source
        self.repositories = repositories
        self.options = options
        self.clock = clock
        self.answer_time = answer_time
        self.jobs: dict[str, SearchJob] = {}
        self.running: dict[str, SearchJob] = {}
        self.queries: dict[str, NameQuery] = {}
        self.waiting: list[NameQuery] = []
        self.active = 0
        self.slot_freed = asyncio.Event()
        self.tasks: set[asyncio.Task[None]] = set()

    def start(
        self,
        *,
        mode: SearchMode,
        kind: Kind,
        title: str,
        names: Sequence[str],
        groups: Sequence[TrackerGroup],
        refresh: bool,
    ) -> SearchJob:
        """The search running with the same names, kind and groups of trackers, or a new one:
        one request per name and group. With `refresh`, the answers kept in the cache are not
        read."""
        self.forget_finished()
        wanted: dict[str, str] = {}
        for name in names:
            wanted.setdefault(normalize(clean_query(name)), name)
        asked = ";".join(
            f"{','.join(map(str, g.categories))}:{','.join(map(str, g.indexer_ids))}"
            for g in groups
        )
        key = f"{mode}|{kind}|{'|'.join(wanted)}|{asked}"
        running = self.running.get(key)
        if running is not None:
            running.followers += 1
            running.notify()
            return running
        job = SearchJob(id=secrets.token_urlsafe(12), key=key, mode=mode, kind=kind, title=title)
        for name in wanted.values() if groups else ():
            query = clean_query(name)
            queries: list[NameQuery] = []
            for group in groups:
                qkey = query_key(query, group.categories, group.indexer_ids)
                name_query = self.queries.get(qkey)
                if name_query is None:
                    name_query = NameQuery(
                        key=qkey,
                        query=query,
                        categories=group.categories,
                        indexer_ids=group.indexer_ids,
                        owner=job.id,
                    )
                    self.queries[qkey] = name_query
                    # In the queue from now: a search shows its place as soon as it starts.
                    self.waiting.append(name_query)
                    self.spawn(self.fetch(name_query, refresh=refresh))
                name_query.jobs.append(job)
                queries.append(name_query)
            job.names.append((name, tuple(queries)))
        self.jobs[job.id] = job
        self.running[key] = job
        self.spawn(self.follow(job))
        return job

    def get(self, search_id: str) -> SearchJob:
        job = self.jobs.get(search_id)
        if job is None:
            raise SearchNotFoundError
        return job

    def spawn(self, coroutine: Coroutine[Any, Any, None]) -> None:
        task = asyncio.get_running_loop().create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def follow(self, job: SearchJob) -> None:
        for name_query in job.queries():
            await name_query.done.wait()
        job.finished_at = self.clock.now()
        self.running.pop(job.key, None)
        job.notify()

    async def fetch(self, name_query: NameQuery, *, refresh: bool) -> None:
        try:
            cached = (
                None if refresh else await anyio.to_thread.run_sync(self.read_cached, name_query)
            )
            if cached is not None:
                name_query.releases, name_query.fetched_at = cached
                name_query.state = "done"
                return
            await self.take_slot(name_query)
            try:
                name_query.state = "running"
                self.changed(name_query)
                with anyio.fail_after(self.options.timeout_seconds):
                    found = await self.source.search(
                        name_query.query, name_query.categories, name_query.indexer_ids
                    )
            finally:
                self.free_slot()
            name_query.releases = tuple(found)
            name_query.fetched_at = self.clock.now()
            name_query.state = "done"
            keep = await self.answer_time.release_answer_seconds()
            await anyio.to_thread.run_sync(self.save, name_query, keep)
        except (ProwlarrError, TimeoutError) as exc:
            logger.info("Prowlarr search failed", extra={"error": type(exc).__name__})
            name_query.state = "failed"
        finally:
            if name_query in self.waiting:
                # Found in the cache, or failed before its turn: the next one may go.
                self.waiting.remove(name_query)
                self.wake()
            self.queries.pop(name_query.key, None)
            name_query.done.set()
            self.changed(name_query)

    async def take_slot(self, name_query: NameQuery) -> None:
        """Wait in the queue (entered when the search started), first come first served, for
        one of the `parallel` slots."""
        while self.active >= self.options.parallel or self.waiting[0] is not name_query:
            await self.slot_freed.wait()
        self.waiting.remove(name_query)
        self.active += 1
        # The next one in the queue may have looked while this one was first: it looks again.
        self.wake()
        self.queue_moved()

    def free_slot(self) -> None:
        self.active -= 1
        self.wake()

    def wake(self) -> None:
        """The requests in the queue look again whether their turn came."""
        event, self.slot_freed = self.slot_freed, asyncio.Event()
        event.set()

    def changed(self, name_query: NameQuery) -> None:
        for job in name_query.jobs:
            job.notify()

    def queue_moved(self) -> None:
        for job in self.running.values():
            job.notify()

    def read_cached(self, name_query: NameQuery) -> tuple[tuple[FoundRelease, ...], float] | None:
        repository = self.repositories()
        try:
            return repository.read_answer(name_query.key, int(self.clock.now()))
        finally:
            repository.close()

    def save(self, name_query: NameQuery, keep: int) -> None:
        """The answer to a name, kept `keep` seconds."""
        now = self.clock.now()
        repository = self.repositories()
        try:
            repository.remove_expired_answers(int(now))
            repository.save_answer(
                name_query.key,
                name_query.releases,
                name_query.fetched_at or now,
                int(now) + keep,
            )
            repository.commit()
        finally:
            repository.close()

    def forget_finished(self) -> None:
        limit = self.clock.now() - self.options.keep_seconds
        for search_id, job in list(self.jobs.items()):
            if job.finished_at is not None and job.finished_at < limit:
                del self.jobs[search_id]

    def progress(self, job: SearchJob) -> SearchProgress:
        states = [name_query.state for name_query in job.queries()]
        state: SearchState
        if job.finished_at is not None:
            state = "failed" if states and all(s == "failed" for s in states) else "done"
        elif any(s in ("running", "done") for s in states):
            state = "running"
        else:
            state = "queued"
        fetched = [q.fetched_at for q in job.queries() if q.fetched_at is not None]
        return SearchProgress(
            id=job.id,
            mode=job.mode,
            kind=job.kind,
            title=job.title,
            state=state,
            names=tuple(
                NameProgress(
                    name=name,
                    state=name_state(queries),
                    found=sum(len(q.releases) for q in queries),
                )
                for name, queries in job.names
            ),
            queued_ahead=self.ahead_of(job),
            followers=job.followers,
            fetched_at=min(fetched) if fetched else None,
        )

    def ahead_of(self, job: SearchJob) -> int:
        """While `job` waits: the other searches running, or with a name in the queue before
        its first one."""
        mine = {id(q) for q in job.queries()}
        for position, name_query in enumerate(self.waiting):
            if id(name_query) in mine:
                running = {q.owner for q in self.queries.values() if q.state == "running"}
                ahead = running | {q.owner for q in self.waiting[:position]}
                return len(ahead - {job.id})
        return 0

    def answers(self, job: SearchJob) -> list[tuple[str, tuple[FoundRelease, ...]]]:
        """Each name with what its requests found, those of the groups merged in their order."""
        found: list[tuple[str, tuple[FoundRelease, ...]]] = []
        for name, queries in job.names:
            done = [q for q in queries if q.state == "done"]
            if done:
                found.append((name, tuple(r for q in done for r in q.releases)))
        return found

    def find(self, guids: Callable[[str], bool]) -> FoundRelease | None:
        """A release of a search kept whose guid `guids` accepts, the newest search first."""
        for job in reversed(list(self.jobs.values())):
            for _, releases in self.answers(job):
                for release in releases:
                    if guids(release.guid):
                        return release
        return None

    async def watch(self, job: SearchJob) -> AsyncIterator[SearchProgress]:
        """The progress of `job` now, then at each change, until it is finished."""
        while True:
            event = job.changed
            yield self.progress(job)
            if job.finished_at is not None:
                return
            await event.wait()
