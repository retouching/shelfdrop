"""The series of the libraries of Jellyfin as the page Métadonnées shows and changes them."""

from dataclasses import dataclass
from typing import Literal

from shelfdrop.works.types import Kind

type ScanMode = Literal["new", "missing", "all"]


@dataclass(frozen=True, kw_only=True)
class LibrarySeries:
    """The folder of a series in a library of Jellyfin and its volumes (the books under it)."""

    id: str
    """The id of its folder in Jellyfin."""
    kind: Kind
    name: str
    original_title: str
    authors: tuple[str, ...]
    """Those of its folder, else those of its volumes."""
    year: int | None
    genres: tuple[str, ...]
    summary: str
    has_image: bool
    volumes: int
    volumes_without_summary: int
    volumes_without_image: int
    path: str
    """Its folder, as Jellyfin sees it."""


@dataclass(frozen=True, kw_only=True)
class VolumeImage:
    """The image Jellyfin holds for a volume (read from its CBZ, its EPUB or its M4B)."""

    item_id: str
    label: str
    """'Tome 3 · CBZ'."""


@dataclass(frozen=True, kw_only=True)
class SourceCover:
    source: str
    url: str


@dataclass(frozen=True, kw_only=True)
class SourceSummary:
    source: str
    text: str


@dataclass(frozen=True, kw_only=True)
class SeriesProposals:
    """What the page proposes for a series: the images of its volumes, then the covers and the
    summaries of the work the sources found under its name."""

    volumes: tuple[VolumeImage, ...]
    covers: tuple[SourceCover, ...]
    summaries: tuple[SourceSummary, ...]
    work_id: str | None
    """The work the sources found, None without one."""


@dataclass(frozen=True, kw_only=True)
class ItemImage:
    """The image of a volume of Jellyfin."""

    item_id: str


@dataclass(frozen=True, kw_only=True)
class LinkImage:
    """An image at an address (a source, or a link given)."""

    url: str


@dataclass(frozen=True, kw_only=True)
class SentImage:
    """An image sent with the change."""

    data: bytes


type ImageChoice = ItemImage | LinkImage | SentImage


@dataclass(frozen=True, kw_only=True)
class SeriesChange:
    """The fields of a series, set and locked in Jellyfin, its summary copied on its volumes
    without one, its image set on it and on its volumes without one, and written as its
    `cover.jpg` by the placement worker."""

    name: str
    original_title: str
    authors: tuple[str, ...]
    year: int | None
    genres: tuple[str, ...]
    summary: str
    lock: bool
    summary_to_volumes: bool
    image: ImageChoice | None
    image_to_series: bool
    image_to_volumes: bool
    save_cover: bool


@dataclass(frozen=True, kw_only=True)
class ScanOrder:
    """A scan of Jellyfin: a series, a library of a kind, or every library (both None)."""

    mode: ScanMode
    kind: Kind | None = None
    series_id: str | None = None
