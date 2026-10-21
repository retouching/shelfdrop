"""Types of the placement: what a download places, where, and what the shelf already holds."""

from dataclasses import dataclass
from typing import Final, Literal

from shelfdrop.works.types import Kind

# Why a download is not placed alone: Ranger takes it (plan section 3, point 5).
type Unplaced = Literal[
    "chapters",
    "no_volume",
    "unknown_author",
    "no_files",
    "missing_files",
    "link_refused",
    "merge_failed",
]
type TaskKind = Literal["cover"]

# The tag of qBittorrent on what shelfdrop placed: the cron of the user leaves it alone.
PLACED_TAG: Final = "placé"
# The folder names of the libraries as the journal and the page name them, without Jellyfin.
LIBRARY_NAMES: Final[dict[Kind, str]] = {
    "manga": "BD & Mangas",
    "ebook": "Livres",
    "audiobook": "Livres audio",
}


@dataclass(frozen=True, kw_only=True)
class ShelfContent:
    """The volumes and the chapters a series folder holds."""

    volumes: frozenset[int]
    chapters: frozenset[float]


@dataclass(frozen=True, kw_only=True)
class PlacedFile:
    """A file put on the shelf: where, and what it is."""

    download_id: int | None
    kind: Kind
    work_id: str | None
    series: str
    author: str
    volume: int | None
    chapter: float | None
    path: str
    """As the placement sees it (`/data/files/comics/...`)."""


@dataclass(frozen=True, kw_only=True)
class ShelfFile:
    """A file on the shelf, as `files` keeps it."""

    id: int
    kind: Kind
    work_id: str | None
    series: str
    author: str
    volume: int | None
    chapter: float | None
    path: str
    locked: bool
    created_at: int


@dataclass(frozen=True, kw_only=True)
class Placement:
    """What a download put on the shelf."""

    destination: str
    """The name of its library, then its series (`shelfdrop.placement.paths.SEPARATOR`)."""
    files: tuple[PlacedFile, ...]
    volumes: tuple[int, ...]
    present: tuple[int, ...]
    """The volumes already on the shelf, left as they are."""
    cover: bytes | None


@dataclass(frozen=True, kw_only=True)
class LibraryTask:
    """A write in a library asked by the API (which never writes there): a `cover.jpg`."""

    id: int
    kind: TaskKind
    path: str
    data: bytes


@dataclass(frozen=True, kw_only=True)
class ComicInfo:
    """What the `ComicInfo.xml` of a merged volume says."""

    series: str
    number: int
    writers: tuple[str, ...] = ()
    summary: str = ""
    title: str = ""


@dataclass(frozen=True, kw_only=True)
class PlacementOptions:
    # Seconds between two rounds of the worker.
    every_seconds: float = 30.0
    # A file placed is looked for in Jellyfin, to lock its metadata, this long at most.
    lock_seconds: int = 24 * 3600
