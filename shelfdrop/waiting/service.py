"""WaitingService: the searches kept waiting. Each is searched again
at the interval of the settings, under every name of its work, in the queue of the other
searches; a release that answers makes it `found`, on the page and in the journal; nothing is
downloaded alone. A volume placed, or chapters placed past their end, leave the list; a search
of chapters moves to the first chapter not placed."""

import logging
from collections.abc import Callable, Sequence
from typing import Protocol

import anyio
import anyio.to_thread

from shelfdrop.journal.types import NewEvent
from shelfdrop.placement.repository import PlacementRepository
from shelfdrop.releases.types import Release
from shelfdrop.waiting.exceptions import WaitingNotFoundError
from shelfdrop.waiting.matching import found, is_done, label, next_chapter
from shelfdrop.waiting.repository import WaitingRepository, WaitingRepositoryFactory
from shelfdrop.waiting.types import (
    Waiting,
    WaitingOptions,
    WaitingState,
    WaitingView,
    WaitOrder,
    Wanted,
)
from shelfdrop.works.types import Clock, Kind

logger = logging.getLogger(__name__)


class ReleaseSearcher(Protocol):
    """A search of releases under the names of a work, to its end: the releases scored and
    filtered as the page shows them."""

    async def releases(self, kind: Kind, title: str, names: Sequence[str]) -> list[Release]: ...


class LibraryVolumes(Protocol):
    """The volumes of a series already in the library of its kind in Jellyfin."""

    async def volumes_of(self, kind: Kind, name: str) -> set[int]: ...


class WaitingSettings(Protocol):
    async def waiting_seconds(self) -> int: ...


class WaitingEvents(Protocol):
    def record(self, event: NewEvent) -> None: ...


type PlacementRepositoryFactory = Callable[[], PlacementRepository]


def same(a: Waiting, order: WaitOrder, wanted: Wanted) -> bool:
    """A waiting search for the same work (by its id, else its name) and the same thing."""
    work = a.work_id == order.work_id if order.work_id else a.title == order.title
    return work and a.kind == order.kind and a.wanted == wanted


class WaitingService:
    def __init__(
        self,
        repositories: WaitingRepositoryFactory,
        shelf: PlacementRepositoryFactory,
        searcher: ReleaseSearcher,
        library: LibraryVolumes,
        settings: WaitingSettings,
        events: WaitingEvents,
        clock: Clock,
    ) -> None:
        self.repositories = repositories
        self.shelf = shelf
        self.searcher = searcher
        self.library = library
        self.settings = settings
        self.events = events
        self.clock = clock

    async def run[T](self, work: Callable[[WaitingRepository], T]) -> T:
        def call() -> T:
            repository = self.repositories()
            try:
                result = work(repository)
                repository.commit()
                return result
            finally:
                repository.close()

        return await anyio.to_thread.run_sync(call)

    async def read(self) -> list[WaitingView]:
        every = await self.settings.waiting_seconds()
        waiting = await self.run(lambda r: r.read_active())
        return [self.view(w, every) for w in waiting]

    def view(self, waiting: Waiting, every: int) -> WaitingView:
        searched = waiting.searched_at
        return WaitingView(
            waiting=waiting,
            next_search_at=int(self.clock.now()) if searched is None else searched + every,
        )

    async def add(self, order: WaitOrder) -> tuple[list[WaitingView], int]:
        """A waiting search for each thing wanted, but those already waiting; the searches added
        and the number left out."""
        now = int(self.clock.now())

        def add(repository: WaitingRepository) -> tuple[list[Waiting], int]:
            active = repository.read_active()
            added: list[Waiting] = []
            skipped = 0
            for wanted in dict.fromkeys(order.wanted):
                if any(same(a, order, wanted) for a in [*active, *added]):
                    skipped += 1
                    continue
                added.append(
                    repository.add(
                        work_id=order.work_id,
                        title=order.title,
                        author=order.author,
                        kind=order.kind,
                        names=order.names,
                        wanted=wanted,
                        now=now,
                        created_by=order.created_by,
                    )
                )
            return added, skipped

        added, skipped = await self.run(add)
        every = await self.settings.waiting_seconds()
        return [self.view(w, every) for w in added], skipped

    async def remove(self, waiting_id: int) -> None:
        now = int(self.clock.now())

        def remove(repository: WaitingRepository) -> None:
            if repository.read(waiting_id) is None:
                raise WaitingNotFoundError(waiting_id)
            repository.mark_done(waiting_id, now)

        await self.run(remove)

    async def search(self, waiting_id: int) -> WaitingView:
        """A search now; raises WaitingNotFoundError."""
        waiting = await self.run(lambda r: r.read(waiting_id))
        if waiting is None:
            raise WaitingNotFoundError(waiting_id)
        searched = await self.search_one(waiting)
        return self.view(searched, await self.settings.waiting_seconds())

    async def search_one(self, waiting: Waiting) -> Waiting:
        releases = await self.searcher.releases(waiting.kind, waiting.title, waiting.names)
        count = found(waiting.wanted, releases)
        state: WaitingState = "found" if count else "waiting"
        now = int(self.clock.now())
        await self.run(lambda r: r.mark_searched(waiting.id, state, count, now))
        if state == "found" and waiting.state != "found":
            event = NewEvent(
                type="found",
                group=f"found:{waiting.kind}:{waiting.title}",
                facts={"work": waiting.title, "target": label(waiting.wanted), "releases": count},
            )
            await anyio.to_thread.run_sync(self.events.record, event)
        read = await self.run(lambda r: r.read(waiting.id))
        return read if read is not None else waiting

    async def tidy(self) -> None:
        """The searches whose volume or chapters are placed leave the list; a search of
        chapters moves to the first chapter not placed."""
        now = int(self.clock.now())

        def placed(waiting: Waiting) -> tuple[set[int], set[float]]:
            repository = self.shelf()
            try:
                files = repository.read_shelved(waiting.work_id, waiting.title, waiting.kind)
            finally:
                repository.close()
            return (
                {f.volume for f in files if f.volume is not None and f.chapter is None},
                {f.chapter for f in files if f.chapter is not None},
            )

        def tidy(repository: WaitingRepository) -> None:
            for waiting in repository.read_active():
                if waiting.wanted.target == "any":
                    continue
                volumes, chapters = placed(waiting)
                if is_done(waiting.wanted, volumes, chapters):
                    repository.mark_done(waiting.id, now)
                elif waiting.wanted.target == "chapters" and waiting.wanted.chapter_from:
                    moved = next_chapter(waiting.wanted.chapter_from, chapters)
                    if moved != waiting.wanted.chapter_from:
                        repository.advance(waiting.id, moved)

        await self.run(tidy)

    async def round(self) -> int:
        """The list tidied, then every search due searched, one after another; how many."""
        await self.tidy()
        due = [
            v.waiting
            for v in await self.read()
            if v.waiting.searched_at is None or v.next_search_at <= int(self.clock.now())
        ]
        for waiting in due:
            try:
                await self.search_one(waiting)
            except Exception:
                logger.exception("Waiting search failed", extra={"waiting_id": waiting.id})
        return len(due)

    async def owned(self, kind: Kind, title: str, work_id: str | None) -> list[int]:
        """The volumes of a work already placed or in its library: those the page does not
        propose."""

        def placed() -> set[int]:
            repository = self.shelf()
            try:
                files = repository.read_shelved(work_id, title, kind)
            finally:
                repository.close()
            return {f.volume for f in files if f.volume is not None and f.chapter is None}

        volumes = await anyio.to_thread.run_sync(placed)
        try:
            volumes |= await self.library.volumes_of(kind, title)
        except Exception:
            logger.info("Library volumes not read", exc_info=True)
        return sorted(volumes)


class WaitingRunner:
    """The rounds of the waiting searches in the API, every `every_seconds`, until stopped (a
    singleton, run by the lifespan)."""

    def __init__(self, service: WaitingService, options: WaitingOptions) -> None:
        self.service = service
        self.every_seconds = options.every_seconds

    async def run(self) -> None:
        while True:
            try:
                await self.service.round()
            except Exception:
                logger.exception("Waiting round failed")
            await anyio.sleep(self.every_seconds)
