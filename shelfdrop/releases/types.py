"""Types of the release search: a release as Prowlarr gives it, the trackers, the filter rules,
and a release as the page shows it."""

from dataclasses import dataclass
from typing import Literal

from shelfdrop.works.types import Kind

type SearchMode = Literal["work", "manual"]
type NameState = Literal["queued", "running", "done", "failed"]
type SearchState = Literal["queued", "running", "done", "failed"]
type Rejection = Literal["relevance", "score"]

# The Prowlarr categories of each kind for a tracker whose categories were never chosen;
# Prowlarr adds the categories of each tracker it maps to them.
DEFAULT_CATEGORIES: dict[Kind, tuple[int, ...]] = {
    "manga": (7030,),  # Books/Comics
    "ebook": (7020,),  # Books/EBook
    "audiobook": (3030,),  # Audio/Audiobook
}

# The names of the standard categories of Prowlarr (Newznab) of the books and the audio, for a
# category chosen or by default that the indexers were not read for yet.
STANDARD_CATEGORIES: dict[int, str] = {
    3000: "Audio",
    3010: "Audio/MP3",
    3020: "Audio/Video",
    3030: "Audio/Audiobook",
    3040: "Audio/Lossless",
    3050: "Audio/Other",
    3060: "Audio/Foreign",
    7000: "Books",
    7010: "Books/Mags",
    7020: "Books/EBook",
    7030: "Books/Comics",
    7040: "Books/Technical",
    7050: "Books/Other",
    7060: "Books/Foreign",
}


@dataclass(frozen=True, kw_only=True)
class Volumes:
    """The volumes a release holds: one, a range (a pack), every one (a complete edition), or
    unknown."""

    kind: Literal["single", "range", "complete", "unknown"]
    first: int | None = None
    last: int | None = None


@dataclass(frozen=True, kw_only=True)
class Chapters:
    """The chapters a name holds: one (`last` is None) or a range; `.5` chapters are numbers
    too."""

    first: float
    last: float | None = None


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
    download_url: str | None = None
    """Where Prowlarr gives its torrent: its download link without the key, or a magnet link.
    Kept on the server alone (ADR 0011)."""


@dataclass(frozen=True, kw_only=True)
class Category:
    """A category an indexer of Prowlarr knows: a standard one (Newznab, under 100000) or one
    of its own (100000 and over, "Literature" of Nyaa); a sub-category carries the name of
    its parent ("Books/Comics")."""

    id: int
    name: str


@dataclass(frozen=True, kw_only=True)
class Indexer:
    """An indexer of Prowlarr (`GET /api/v1/indexer`)."""

    id: int
    name: str
    enabled: bool
    language: str | None
    protocol: str
    categories: tuple[Category, ...] = ()
    """Its categories (`capabilities.categories`), the sub-categories flattened."""


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
    available: tuple[Category, ...] = ()
    """The categories Prowlarr gave for it at its last read."""
    chosen: dict[Kind, tuple[int, ...]] | None = None
    """The categories searched for each kind, as chosen; None: never chosen, the defaults. A
    kind left out takes its default; an empty list: the tracker is not asked for that kind."""


@dataclass(frozen=True, kw_only=True)
class TrackerChoice:
    """What the page chose for a tracker: asked, automatic, and its categories by kind (None:
    kept as they were)."""

    indexer_id: int
    used: bool
    auto: bool
    categories: dict[Kind, tuple[int, ...]] | None = None


@dataclass(frozen=True, kw_only=True)
class TrackerGroup:
    """Trackers searched together for a kind: those that search the same categories."""

    categories: tuple[int, ...]
    indexer_ids: tuple[int, ...]


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
    automatic: bool
    """Kept, from a tracker allowed for the automatic downloads: an automatic download may
    take it."""
    download_url: str | None
    """Where Prowlarr gives its torrent (`FoundRelease.download_url`); never sent to a page."""


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
class Torrent:
    """The torrent of a release, as Prowlarr gives it: a `.torrent` file, or a magnet link."""

    file: bytes | None = None
    magnet: str | None = None


@dataclass(frozen=True, kw_only=True)
class ReleaseOptions:
    # Prowlarr searches at the same time; the next ones wait in a queue.
    parallel: int = 2
    # A Prowlarr search that has not answered after this many seconds failed.
    timeout_seconds: float = 60.0
    # A finished search can be read by its id for this many seconds.
    keep_seconds: int = 600
