"""Types of the placement: what a download places, where, and what the shelf already holds."""

from dataclasses import dataclass
from typing import Final, Literal

from shelfdrop.works.types import Kind

# Why a download is not placed alone: Ranger takes it.
type Unplaced = Literal[
    "chapters",
    "no_volume",
    "unknown_author",
    "no_files",
    "missing_files",
    "link_refused",
    "merge_failed",
    "exists",
]
# A write the API asks the worker for: a `cover.jpg`, or a scan of the libraries.
type TaskKind = Literal["cover", "scan"]
# Where a file of Ranger comes from: a download (hardlinked), the libraries (moved).
type ItemOrigin = Literal["download", "library", "upload"]
# A file of Ranger: to link to a work, a release in chapters to link to volumes, a file of the
# libraries misplaced, placed, or ignored (left where it is, out of the files to place).
type ItemState = Literal["unlinked", "chapters", "misplaced", "placed", "ignored"]
# Why the scan found a file misplaced: at the root of its library, out of the names of the
# shelf, MP3 tracks not merged, a folder of chapters.
type Misplaced = Literal["root", "naming", "tracks", "chapters"]
type Rest = Literal["place", "keep"]

# The tag of qBittorrent on what shelfdrop placed: a tool that places on its own may leave it alone.
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


@dataclass(frozen=True, kw_only=True)
class NewItem:
    """A file (or a folder of files) to place by hand, as the worker found it."""

    origin: ItemOrigin
    download_id: int | None
    kind: Kind | None
    name: str
    path: str
    files: tuple[str, ...]
    size: int
    state: ItemState
    reason: str | None
    chapters: tuple[float, ...] = ()
    series: str = ""
    existing: tuple[int, ...] = ()
    """The volumes of `series` on the shelf."""
    work_id: str | None = None
    author: str = ""
    loose: tuple[float, ...] = ()
    """The chapters loose in the folder of `series`, out of `files`."""


@dataclass(frozen=True, kw_only=True)
class VolumeRequest:
    """One volume: a manga `<Series> - TXX`, a book or an audiobook under its author."""

    type: Literal["volume"] = "volume"
    kind: Kind
    work_id: str | None
    series: str
    author: str
    volume: int | None
    title: str = ""


@dataclass(frozen=True, kw_only=True)
class ChapterRequest:
    """One file of chapters of a manga (`first` to `last`), in a volume or in none."""

    type: Literal["chapter"] = "chapter"
    work_id: str | None
    series: str
    author: str
    first: float
    last: float | None = None
    volume: int | None = None


@dataclass(frozen=True, kw_only=True)
class VolumeRange:
    """The chapters of one real volume, `first` to `last`, even those the release lacks."""

    volume: int
    first: float
    last: float
    replace: bool = False


@dataclass(frozen=True, kw_only=True)
class ChaptersRequest:
    """A release in chapters linked to its volumes: a complete one merged into one CBZ, the
    chapters of an incomplete one placed as they are, the rest placed without a volume or
    kept in Ranger."""

    type: Literal["chapters"] = "chapters"
    work_id: str | None
    series: str
    author: str
    summary: str = ""
    volumes: tuple[VolumeRange, ...]
    rest: Rest = "keep"


@dataclass(frozen=True, kw_only=True)
class IgnoreRequest:
    """The file left where it is: out of the files to place, nothing written nor removed."""

    type: Literal["ignore"] = "ignore"


type PlaceRequest = VolumeRequest | ChapterRequest | ChaptersRequest | IgnoreRequest


@dataclass(frozen=True, kw_only=True)
class PlaceItem:
    """A file of Ranger, as `place_items` keeps it."""

    id: int
    origin: ItemOrigin
    download_id: int | None
    kind: Kind | None
    name: str
    path: str
    files: tuple[str, ...]
    size: int
    state: ItemState
    reason: str | None
    chapters: tuple[float, ...]
    series: str
    existing: tuple[int, ...]
    loose: tuple[float, ...]
    work_id: str | None
    author: str
    request: PlaceRequest | None
    error: str | None
    destination: str | None
    created_at: int
    updated_at: int
