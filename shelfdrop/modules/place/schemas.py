"""Request and response schemas of the place module (the page Ranger)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from shelfdrop.placement.types import ItemOrigin, ItemState, Rest
from shelfdrop.works.types import Kind

type ShortText = Annotated[str, StringConstraints(max_length=200)]
type Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
type Chapter = Annotated[float, Field(ge=0, le=99999)]
type Volume = Annotated[int, Field(ge=1, le=9999)]


class VolumeBody(BaseModel):
    """One volume: a manga `<Series> - TXX`, a book or an audiobook under its author."""

    type: Literal["volume"] = "volume"
    kind: Kind
    work_id: ShortText | None = None
    series: Name
    author: ShortText = ""
    volume: Volume | None = None
    title: ShortText = ""


class ChapterBody(BaseModel):
    """One file of chapters of a manga, `first` to `last`, in a volume or in none."""

    type: Literal["chapter"]
    work_id: ShortText | None = None
    series: Name
    author: ShortText = ""
    first: Chapter
    last: Chapter | None = None
    volume: Volume | None = None


class VolumeRangeBody(BaseModel):
    volume: Volume
    first: Chapter
    last: Chapter
    # A volume already on the shelf is replaced only when checked.
    replace: bool = False


class ChaptersBody(BaseModel):
    """A release in chapters linked to its volumes; the rest placed without a volume, or kept."""

    type: Literal["chapters"]
    work_id: ShortText | None = None
    series: Name
    author: ShortText = ""
    summary: Annotated[str, StringConstraints(max_length=5000)] = ""
    volumes: list[VolumeRangeBody] = Field(max_length=500)
    rest: Rest = "keep"


class IgnoreBody(BaseModel):
    """The file left where it is: out of the files to place, nothing written nor removed."""

    type: Literal["ignore"]


type PlaceBody = Annotated[
    VolumeBody | ChapterBody | ChaptersBody | IgnoreBody, Field(discriminator="type")
]


class ItemRead(BaseModel):
    # `item-<n>` for a file of Ranger, `shelf-<n>` for a file of the shelf.
    id: str
    origin: ItemOrigin
    kind: Kind | None
    name: str
    path: str
    size: int
    # `unlinked`, `chapters`, `misplaced`, `placed` or `ignored`; `placing` while the worker
    # has it.
    state: ItemState | Literal["placing"]
    # Why it is in Ranger: why its download was not placed (`chapters`, `manual`,
    # `no_volume`...), or why the scan found it (`root`, `naming`, `tracks`, `chapters`).
    reason: str | None
    # Why the last request failed (`exists`, `link_refused`, `copy_failed`, `merge_failed`...).
    error: str | None
    destination: str | None
    chapters: list[float]
    # The volumes of `series` on the shelf.
    existing: list[int]
    # The chapters loose in the folder of `series`, out of its files: a volume of a release in
    # chapters is complete with them too, and merged (they are removed).
    loose: list[float]
    series: str
    author: str
    work_id: str | None
    # Placed through a copy of a file of its download rather than a hardlink
    # (`placement.mode`).
    copied: bool


class ItemsRead(BaseModel):
    items: list[ItemRead]
    # The files to place: the counter of the page.
    open: int
