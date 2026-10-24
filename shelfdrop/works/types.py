"""Types of the work search: a work as one source sees it, and a work merged from every source."""

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

type Kind = Literal["manga", "ebook", "audiobook"]
type Family = Literal["manga", "book"]
type Form = Literal["manga", "novel", "anthology", "doujinshi", "oneshot", "other"]

# "fr", "en", "ja-ro" (romaji), "ja", "ko", "zh", "ru", ... or "latin" when a source gives a
# name in the Latin script without saying which language it is in.
type Language = str

type SourceName = Literal[
    "mangaupdates", "kitsu", "myanimelist", "anilist", "mangadex", "bnf", "openlibrary", "wikidata"
]


def family_of(kind: Kind) -> Family:
    return "manga" if kind == "manga" else "book"


@dataclass(frozen=True, kw_only=True)
class Name:
    title: str
    language: Language


@dataclass(frozen=True, kw_only=True)
class Candidate:
    """One work as one source sees it."""

    source: SourceName
    source_id: str
    title: str
    names: tuple[Name, ...] = ()
    authors: tuple[str, ...] = ()
    year: int | None = None
    volumes: int | None = None
    """Volumes of the original edition."""
    volumes_fr: int | None = None
    """Volumes published in France (BnF only)."""
    form: Form = "other"
    cover_url: str | None = None
    isbns: tuple[str, ...] = ()
    external_ids: Mapping[str, str] = field(default_factory=dict)
    """Ids of the same work at other sources, by source name (e.g. {"myanimelist": "116778"})."""
    popularity: float = 0.0
    """0 to 1, only to break ties between equally good matches."""
    url: str | None = None
    summary: str = ""
    """Its summary at the source, without markup."""


@dataclass(frozen=True, kw_only=True)
class NameChoice:
    title: str
    language: Language
    checked: bool
    """Searched on Prowlarr by default."""
    sources: tuple[SourceName, ...] = ()
    """The sources that gave it, the most trusted first (`TitleOrder.sources`); none in the
    works cached before they were kept."""

    @property
    def source(self) -> SourceName | None:
        """The most trusted source that gave it."""
        return self.sources[0] if self.sources else None


@dataclass(frozen=True, kw_only=True)
class TitleOrder:
    """The orders the title of a work and its name on the shelf are chosen by (the settings
    `search.language_order` and `search.source_order`): its languages, the first wanted first
    ("latin": a name of a language not known), and its sources, the most trusted first. The
    defaults are those of the search before the settings."""

    languages: tuple[Language, ...] = ("fr", "en", "ja-ro", "latin")
    sources: tuple[SourceName, ...] = (
        "myanimelist",
        "anilist",
        "mangaupdates",
        "kitsu",
        "mangadex",
        "openlibrary",
        "wikidata",
        "bnf",
    )


@dataclass(frozen=True, kw_only=True)
class WorkPart:
    """One of the works a merge by hand joined, as the search found it alone."""

    id: str
    title: str
    authors: tuple[str, ...]
    sources: tuple[SourceName, ...]


@dataclass(frozen=True, kw_only=True)
class Work:
    """A work merged from every source that knows it."""

    id: str
    title: str
    shelf_name: str
    """Name used in the library: the French edition's title when there is one."""
    authors: tuple[str, ...]
    year: int | None
    volumes: int | None
    volumes_fr: int | None
    form: Form
    names: tuple[NameChoice, ...]
    sources: tuple[SourceName, ...]
    cover_url: str | None
    isbns: tuple[str, ...]
    links: Mapping[str, str]
    """Page of the work at each source, by source name."""
    covers: Mapping[str, str] = field(default_factory=dict)
    """The cover at each source that has one, by source name."""
    summaries: Mapping[str, str] = field(default_factory=dict)
    """The summary at each source that has one, by source name."""
    keys: tuple[str, ...] = ()
    """The key of each of its members, `<source>:<id at that source>`."""
    merge_id: int | None = None
    """The merge by hand it comes from, when the page joined several works into it."""
    parts: tuple[WorkPart, ...] = ()
    """The works that merge joined, in their order."""


@dataclass(frozen=True, kw_only=True)
class WorkMerge:
    """Works joined by hand: the keys of their members, applied to
    every search of the family after, and the name on the shelf chosen."""

    id: int
    family: Family
    keys: tuple[str, ...]
    shelf_name: str


@dataclass(frozen=True, kw_only=True)
class WorkSearch:
    query: str
    kind: Kind
    works: tuple[Work, ...]
    other_forms: tuple[Work, ...]
    """Novels, anthologies, dōjinshi... found for a manga search, shown folded."""
    unavailable: tuple[SourceName, ...]
    """Sources that did not answer; the results come from the others."""


@dataclass(frozen=True, kw_only=True)
class SearchOptions:
    # A source that has not answered after this many seconds is left out of the search.
    source_timeout_seconds: float = 10.0
    # A source that failed this many times in a row is skipped for `source_rest_seconds`.
    failures_to_rest: int = 2
    source_rest_seconds: int = 60
    # A work returned by a search can be read by its id for this many seconds.
    work_seconds: int = 7 * 24 * 3600


class Clock:
    """The time in Unix seconds; the tests replace it."""

    def now(self) -> float:
        return time.time()
