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
    NoSourceAnsweredError,
    QueryTooShortError,
    SourceError,
    WorkNotFoundError,
)
from shelfdrop.works.flights import SearchFlights, SourceHealth
from shelfdrop.works.merge import french_edition_names, merge
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
    WorkSearch,
    family_of,
)

logger = logging.getLogger(__name__)

MIN_QUERY_LENGTH = 2


class MetadataClient(Protocol):
    name: SourceName
    families: frozenset[Family]

    async def search(self, query: str, family: Family) -> list[Candidate]: ...


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
    ) -> None:
        self.repository = repository
        self.sources = sources
        self.flights = flights
        self.health = health
        self.options = options
        self.clock = clock

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
        clients = [client for client in self.sources.clients if family in client.families]
        now = self.clock.now()
        unavailable: list[SourceName] = []
        answers = await self.ask(clients, query, family, now, unavailable)
        if clients and len(unavailable) == len(clients):
            raise NoSourceAnsweredError
        candidates = [c for answer in answers.values() for c in answer.candidates]
        works, other_forms = rank(query, merge(candidates), manga=family == "manga")
        bnf = [c for c in clients if c.name == "bnf" and c.name not in unavailable]
        names = french_edition_names(works, query) if bnf else []
        if names:
            # The BnF again, under the French names the other sources gave the best works.
            for name in names:
                answers.update(await self.ask(bnf, name, family, now, unavailable))
            candidates = [c for answer in answers.values() for c in answer.candidates]
            works, other_forms = rank(query, merge(candidates), manga=family == "manga")
        order = [client.name for client in clients]
        result = WorkSearch(
            query=query,
            kind=kind,
            works=tuple(works),
            other_forms=tuple(other_forms),
            unavailable=tuple(sorted(set(unavailable), key=order.index)),
        )
        fresh = {key: answer.candidates for key, answer in answers.items() if answer.fresh}
        await anyio.to_thread.run_sync(self.save, fresh, [*works, *other_forms], int(now))
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
    ) -> None:
        """The answers and the works of a search, written in one transaction; the expired rows
        go at the same time."""
        self.repository.remove_expired(now)
        self.repository.save_answers(answers, now + self.options.answer_seconds)
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
