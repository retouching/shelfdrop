"""Types of the release search: a release as Prowlarr gives it, the trackers, the filter rules,
and a release as the page shows it."""

from dataclasses import dataclass
from typing import Literal

from shelfdrop.works.types import Kind

type SearchMode = Literal["work", "manual"]
type NameState = Literal["queued", "running", "done", "failed"]
type SearchState = Literal["queued", "running", "done", "failed"]
type Rejection = Literal["relevance", "score"]

# The Prowlarr categories of each kind; Prowlarr adds the categories of each tracker it maps
# to them.
CATEGORIES: dict[Kind, tuple[int, ...]] = {
    "manga": (7030,),  # Books/Comics
    "ebook": (7020,),  # Books/EBook
    "audiobook": (3030,),  # Audio/Audiobook
}


@dataclass(frozen=True, kw_only=True)
class Volumes:
    """The volumes a release holds: one, a range (a pack), every one (a complete edition), or
    unknown."""

    kind: Literal["single", "range", "complete", "unknown"]
    first: int | None = None
    last: int | None = None


@dataclass(frozen=True, kw_only=True)
class FoundRelease:
    """One release as Prowlarr answers it, without its download link (it carries a key)."""

    guid: str
    title: str
    indexer_id: int
    indexer: str
    size: int
    seeders: int
    info_url: str | None = None
    info_hash: str | None = None
    publish_date: str | None = None


@dataclass(frozen=True, kw_only=True)
class Indexer:
    """An indexer of Prowlarr (`GET /api/v1/indexer`)."""

    id: int
    name: str
    enabled: bool
    language: str | None
    protocol: str


@dataclass(frozen=True, kw_only=True)
class Tracker:
    """An indexer of Prowlarr as shelfdrop uses it, in the order of the trackers."""

    indexer_id: int
    name: str
    language: str | None
    prowlarr_enabled: bool
    """Off in Prowlarr: listed apart, never asked."""
    used: bool
    """Asked by the searches."""
    auto: bool
    """Allowed for the automatic downloads."""


@dataclass(frozen=True, kw_only=True)
class FilterRule:
    """Points given to a release whose title matches: words (comma-separated, whole words,
    any case) or a regular expression."""

    name: str
    pattern: str
    regex: bool
    score: int
    kinds: tuple[Kind, ...] = ()
    """The kinds it applies to; empty: every kind."""
    enabled: bool = True


@dataclass(frozen=True, kw_only=True)
class Filters:
    rules: tuple[FilterRule, ...]
    minimum: int
    """A release under this score is set aside."""


@dataclass(frozen=True, kw_only=True)
class RuleMatch:
    name: str
    score: int


@dataclass(frozen=True, kw_only=True)
class Release:
    """A release of a search, as the page shows it."""

    id: str
    guid: str
    title: str
    matched_name: str
    """The first name that found it."""
    indexer_id: int
    indexer: str
    indexer_rank: int
    """Its place in the order of the trackers."""
    info_url: str | None
    info_hash: str | None
    seeders: int
    size: int
    volumes: Volumes
    score: int
    score_rules: tuple[RuleMatch, ...]
    rejected: Rejection | None
    """Set aside: its title misses a word of its name, or its score is under the minimum."""


@dataclass(frozen=True, kw_only=True)
class NameProgress:
    name: str
    state: NameState
    found: int


@dataclass(frozen=True, kw_only=True)
class SearchProgress:
    """Where a search is: the state of each name, and the searches ahead of it in the queue."""

    id: str
    mode: SearchMode
    kind: Kind
    title: str
    state: SearchState
    names: tuple[NameProgress, ...]
    queued_ahead: int
    followers: int
    """How many requests asked this search: more than one, it is shared."""
    fetched_at: float | None
    """When the oldest answer was fetched from Prowlarr (a cached one may be minutes old)."""


@dataclass(frozen=True, kw_only=True)
class ReleaseSearch:
    progress: SearchProgress
    releases: tuple[Release, ...]
    minimum: int


@dataclass(frozen=True, kw_only=True)
class ReleaseOptions:
    # Prowlarr searches at the same time; the next ones wait in a queue.
    parallel: int = 2
    # A Prowlarr search that has not answered after this many seconds failed.
    timeout_seconds: float = 60.0
    # The answer of Prowlarr to a name is reused for this many seconds.
    answer_seconds: int = 600
    # A finished search can be read by its id for this many seconds.
    keep_seconds: int = 600
    # At most this many names are searched for a work.
    max_names: int = 6
