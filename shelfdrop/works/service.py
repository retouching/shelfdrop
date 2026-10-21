"""WorkService: the search of a work in every metadata source of its family at once, merged and
ranked, and the read of a work found by a search."""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import anyio
import anyio.to_thread

from shelfdrop.utils.text import normalize
from shelfdrop.works.exceptions import (
    MergeNotFoundError,
    MergeRefusedError,
    NoSourceAnsweredError,
    QueryTooShortError,
    SourceError,
    WorkNotFoundError,
)
from shelfdrop.works.flights import SearchFlights, SourceHealth
from shelfdrop.works.merge import french_edition_names, join_merges, merge
from shelfdrop.works.ranking import rank
from shelfdrop.works.repository import WorkRepository
from shelfdrop.works.types import (
    Candidate,
    Clock,
    Family,
    Kind,
    SearchOptions,
    SourceName,
    Work,
    WorkMerge,
    WorkSearch,
    family_of,
)

logger = logging.getLogger(__name__)

MIN_QUERY_LENGTH = 2
# The longest name on the shelf a merge by hand takes.
MAX_SHELF_NAME = 300


class MetadataClient(Protocol):
    name: SourceName
    families: frozenset[Family]

    async def search(self, query: str, family: Family) -> list[Candidate]: ...


class WorkSettings(Protocol):
    """The settings of the work search, read at each search (the settings page)."""

    async def enabled_sources(self) -> frozenset[str]: ...

    async def work_answer_seconds(self) -> int: ...


@dataclass(frozen=True)
class Answer:
    """What one source answered to one text, and whether it comes from the source itself (to
    keep) rather than from the cache."""

    candidates: tuple[Candidate, ...]
    fresh: bool


@dataclass(frozen=True)
class WorkSources:
    """The metadata clients, in the order their names are listed in `unavailable`."""

    clients: tuple[MetadataClient, ...]


class WorkService:
    def __init__(
        self,
        repository: WorkRepository,
        sources: WorkSources,
        flights: SearchFlights,
        health: SourceHealth,
        options: SearchOptions,
        clock: Clock,
        settings: WorkSettings,
    ) -> None:
        self.repository = repository
        self.sources = sources
        self.flights = flights
        self.health = health
        self.options = options
        self.clock = clock
        self.settings = settings

    async def search(self, query: str, kind: Kind) -> WorkSearch:
        """Every source of the family of `kind` at once. Raises QueryTooShortError, and
        NoSourceAnsweredError when every source failed."""
        query = " ".join(query.split())
        if len(normalize(query).replace(" ", "")) < MIN_QUERY_LENGTH:
            raise QueryTooShortError
        key = f"{kind}|{normalize(query)}"
        running = self.flights.joined(key)
        if running is not None:
            return await asyncio.shield(running)
        future = self.flights.start(key)
        try:
            result = await self.run_search(query, kind)
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()  # retrieved: the requests that joined raise it themselves
            raise
        finally:
            self.flights.end(key)
        future.set_result(result)
        return result

    async def run_search(self, query: str, kind: Kind) -> WorkSearch:
        family = family_of(kind)
        enabled = await self.settings.enabled_sources()
        clients = [
            client
            for client in self.sources.clients
            if family in client.families and client.name in enabled
        ]
        now = self.clock.now()
        unavailable: list[SourceName] = []
        answers = await self.ask(clients, query, family, now, unavailable)
        if clients and len(unavailable) == len(clients):
            raise NoSourceAnsweredError
        merges = await anyio.to_thread.run_sync(self.repository.read_merges, family)
        candidates = [c for answer in answers.values() for c in answer.candidates]
        works, other_forms = rank(
            query, join_merges(merge(candidates), merges), manga=family == "manga"
        )
        bnf = [c for c in clients if c.name == "bnf" and c.name not in unavailable]
        names = french_edition_names(works, query) if bnf else []
        if names:
            # The BnF again, under the French names the other sources gave the best works.
            for name in names:
                answers.update(await self.ask(bnf, name, family, now, unavailable))
            candidates = [c for answer in answers.values() for c in answer.candidates]
            works, other_forms = rank(
                query, join_merges(merge(candidates), merges), manga=family == "manga"
            )
        order = [client.name for client in clients]
        result = WorkSearch(
            query=query,
            kind=kind,
            works=tuple(works),
            other_forms=tuple(other_forms),
            unavailable=tuple(sorted(set(unavailable), key=order.index)),
        )
        fresh = {key: answer.candidates for key, answer in answers.items() if answer.fresh}
        keep = await self.settings.work_answer_seconds()
        await anyio.to_thread.run_sync(self.save, fresh, [*works, *other_forms], int(now), keep)
        return result

    async def ask(
        self,
        clients: Sequence[MetadataClient],
        query: str,
        family: Family,
        now: float,
        unavailable: list[SourceName],
    ) -> dict[tuple[SourceName, str], Answer]:
        """The answers of `clients` to `query`, by source and cache key: the cache first, then
        every other source at once. A source that fails is added to `unavailable`."""
        cache_key = f"{family}|{normalize(query)}"
        cached = await anyio.to_thread.run_sync(
            self.repository.read_answers, [client.name for client in clients], cache_key, int(now)
        )
        answers = {
            (source, cache_key): Answer(candidates=found, fresh=False)
            for source, found in cached.items()
        }

        async def ask_one(client: MetadataClient) -> None:
            if self.health.is_down(client.name, now):
                unavailable.append(client.name)
                return
            try:
                with anyio.fail_after(self.options.source_timeout_seconds):
                    found = tuple(await client.search(query, family))
            except (SourceError, TimeoutError) as exc:
                logger.info(
                    "Metadata source unavailable",
                    extra={"source": client.name, "error": type(exc).__name__},
                )
                self.health.failed(client.name, now + self.options.source_rest_seconds)
                unavailable.append(client.name)
                return
            answers[client.name, cache_key] = Answer(candidates=found, fresh=True)

        async with anyio.create_task_group() as group:
            for client in clients:
                if client.name not in cached:
                    group.start_soon(ask_one, client)
        return answers

    def save(
        self,
        answers: Mapping[tuple[SourceName, str], tuple[Candidate, ...]],
        works: Sequence[Work],
        now: int,
        keep: int,
    ) -> None:
        """The answers (kept `keep` seconds) and the works of a search, written in one
        transaction; the expired rows go at the same time."""
        self.repository.remove_expired(now)
        self.repository.save_answers(answers, now + keep)
        self.repository.save_works(works, now + self.options.work_seconds)
        self.repository.commit()

    async def read_work(self, work_id: str) -> Work:
        """A work a search returned in the last days. Raises WorkNotFoundError."""
        work = await anyio.to_thread.run_sync(
            self.repository.read_work, work_id, int(self.clock.now())
        )
        if work is None:
            raise WorkNotFoundError
        return work

    async def merge_works(self, kind: Kind, work_ids: Sequence[str], shelf_name: str) -> WorkMerge:
        """The works `work_ids` (found by a search, merges included) joined into one under
        `shelf_name`, for every search of the family of `kind` after; the merges they belonged
        to give way to it. Raises WorkNotFoundError, MergeRefusedError."""
        name = " ".join(shelf_name.split())
        ids = list(dict.fromkeys(work_ids))
        if len(ids) < 2 or not name or len(name) > MAX_SHELF_NAME:
            raise MergeRefusedError
        family = family_of(kind)
        now = int(self.clock.now())

        def run() -> WorkMerge:
            works: list[Work] = []
            for work_id in ids:
                work = self.repository.read_work(work_id, now)
                if work is None:
                    raise WorkNotFoundError
                works.append(work)
            keys = tuple(dict.fromkeys(k for w in works for k in (w.keys or (w.id,))))
            joined = set(keys)
            older = [m.id for m in self.repository.read_merges(family) if joined & set(m.keys)]
            self.repository.delete_merges(older)
            merge_id = self.repository.add_merge(family, keys, name, now)
            self.repository.commit()
            return WorkMerge(id=merge_id, family=family, keys=keys, shelf_name=name)

        found = await anyio.to_thread.run_sync(run)
        logger.info("Works merged", extra={"merge": found.id, "works": len(ids)})
        return found

    async def split_works(self, merge_id: int) -> None:
        """The merge `merge_id` undone: the next searches find its works apart again. Raises
        MergeNotFoundError."""

        def run() -> None:
            if self.repository.delete_merges([merge_id]) == 0:
                raise MergeNotFoundError
            self.repository.commit()

        await anyio.to_thread.run_sync(run)
        logger.info("Works split", extra={"merge": merge_id})
