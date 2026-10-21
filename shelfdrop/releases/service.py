"""ReleaseService: the search of releases in Prowlarr, under the names of a work or a text typed,
and the trackers and the filters it uses."""

from collections.abc import AsyncIterator, Sequence
from typing import Final, Protocol

import anyio
import anyio.to_thread

from shelfdrop.releases.clients.prowlarr import ProwlarrClient
from shelfdrop.releases.exceptions import InvalidRuleError, TooManyNamesError
from shelfdrop.releases.jobs import SearchBoard
from shelfdrop.releases.repository import ReleaseRepository
from shelfdrop.releases.results import assemble
from shelfdrop.releases.scoring import invalid_rules
from shelfdrop.releases.trackers import merge_trackers, ordered_choices
from shelfdrop.releases.types import (
    Filters,
    Indexer,
    ReleaseOptions,
    ReleaseSearch,
    SearchMode,
    SearchProgress,
    Tracker,
)
from shelfdrop.utils.text import normalize
from shelfdrop.works.exceptions import QueryTooShortError
from shelfdrop.works.types import Clock, Kind

MINIMUM_KEY: Final = "filters.minimum"
# The minimum score before it is ever saved.
DEFAULT_MINIMUM: Final = -100


class NameLimit(Protocol):
    """How many names a work search may send, read at each search (the settings page)."""

    async def max_names(self) -> int: ...


class ReleaseService:
    """Async throughout: a search runs on the event loop, and the Prowlarr client is an async
    singleton; the repository runs in the threadpool."""

    def __init__(
        self,
        repository: ReleaseRepository,
        board: SearchBoard,
        prowlarr: ProwlarrClient,
        options: ReleaseOptions,
        clock: Clock,
        name_limit: NameLimit,
    ) -> None:
        self.repository = repository
        self.board = board
        self.prowlarr = prowlarr
        self.options = options
        self.clock = clock
        self.name_limit = name_limit

    async def start(
        self, *, mode: SearchMode, kind: Kind, title: str, names: Sequence[str], refresh: bool
    ) -> SearchProgress:
        """A search under `names` (the names of a work) or one text (manual), in the trackers
        asked. Raises QueryTooShortError, TooManyNamesError, and ProwlarrError when the trackers
        were never read and Prowlarr does not answer."""
        names = list(dict.fromkeys(" ".join(n.split()) for n in names if n.strip()))
        if not names or any(len(normalize(n).replace(" ", "")) < 2 for n in names):
            raise QueryTooShortError
        if len(names) > (await self.name_limit.max_names() if mode == "work" else 1):
            raise TooManyNamesError
        trackers = await anyio.to_thread.run_sync(self.repository.read_trackers)
        if not trackers:
            trackers = await self.refresh_trackers()
        indexer_ids = [t.indexer_id for t in trackers if t.used and t.prowlarr_enabled]
        job = self.board.start(
            mode=mode,
            kind=kind,
            title=title,
            names=names,
            indexer_ids=indexer_ids,
            refresh=refresh,
        )
        return self.board.progress(job)

    def progress(self, search_id: str) -> SearchProgress:
        """Raises SearchNotFoundError."""
        return self.board.progress(self.board.get(search_id))

    def watch(self, search_id: str) -> AsyncIterator[SearchProgress]:
        """The progress of a search at each change, until it ends. Raises SearchNotFoundError."""
        return self.board.watch(self.board.get(search_id))

    async def read(self, search_id: str) -> ReleaseSearch:
        """The releases found so far, scored with the filters and ranked with the trackers of
        now. Raises SearchNotFoundError."""
        job = self.board.get(search_id)
        progress = self.board.progress(job)
        answers = self.board.answers(job)
        trackers = await anyio.to_thread.run_sync(self.repository.read_trackers)
        filters = await anyio.to_thread.run_sync(self.filters_saved)
        releases = assemble(
            answers,
            kind=job.kind,
            relevance=job.mode == "work",
            ranks={t.indexer_id: rank for rank, t in enumerate(trackers)},
            filters=filters,
        )
        return ReleaseSearch(progress=progress, releases=tuple(releases), minimum=filters.minimum)

    async def read_trackers(self) -> list[Tracker]:
        return await anyio.to_thread.run_sync(self.repository.read_trackers)

    async def refresh_trackers(self) -> list[Tracker]:
        """The trackers after a read of the indexers of Prowlarr. Raises ProwlarrError."""
        indexers = await self.prowlarr.indexers()
        return await anyio.to_thread.run_sync(self.merge_and_save, indexers)

    def merge_and_save(self, indexers: list[Indexer]) -> list[Tracker]:
        trackers = merge_trackers(self.repository.read_trackers(), indexers)
        self.repository.replace_trackers(trackers)
        self.repository.commit()
        return trackers

    async def save_trackers(self, choices: Sequence[tuple[int, bool, bool]]) -> list[Tracker]:
        """The order and the choices of the trackers: (indexer id, asked, automatic)."""
        return await anyio.to_thread.run_sync(self.order_and_save, choices)

    def order_and_save(self, choices: Sequence[tuple[int, bool, bool]]) -> list[Tracker]:
        trackers = ordered_choices(self.repository.read_trackers(), choices)
        self.repository.replace_trackers(trackers)
        self.repository.commit()
        return trackers

    async def read_filters(self) -> Filters:
        return await anyio.to_thread.run_sync(self.filters_saved)

    def filters_saved(self) -> Filters:
        minimum = self.repository.read_setting(MINIMUM_KEY)
        return Filters(
            rules=self.repository.read_rules(),
            minimum=minimum if isinstance(minimum, int) else DEFAULT_MINIMUM,
        )

    async def save_filters(self, filters: Filters) -> Filters:
        """Raises InvalidRuleError when a rule's expression is empty or invalid."""
        invalid = invalid_rules(filters.rules)
        if invalid:
            raise InvalidRuleError(invalid)
        return await anyio.to_thread.run_sync(self.replace_filters, filters)

    def replace_filters(self, filters: Filters) -> Filters:
        self.repository.replace_rules(filters.rules)
        self.repository.save_setting(MINIMUM_KEY, filters.minimum, int(self.clock.now()))
        self.repository.commit()
        return filters
