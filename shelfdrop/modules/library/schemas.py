"""Request and response schemas of the library module (the page Jellyfin)."""

import base64
import binascii
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from shelfdrop.library.types import NumberOrigin, ScanMode, SyncStage
from shelfdrop.works.types import Kind, SourceName

type ShortText = Annotated[str, StringConstraints(max_length=300)]
# An image sent in base64: 5 MB, a third more.
SENT_MAX: int = 7 * 1024 * 1024


class SeriesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The id of its folder in Jellyfin.
    id: str
    kind: Kind
    name: str
    original_title: str
    authors: list[str]
    year: int | None
    genres: list[str]
    summary: str
    has_image: bool
    volumes: int
    volumes_without_summary: int
    volumes_without_image: int
    # The tag of its image in Jellyfin, which changes with it (null without one): the `tag` of
    # /library/items/{id}/image.
    image_tag: str | None


class LibraryRead(BaseModel):
    series: list[SeriesRead]


class VolumeImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The image is at /library/items/{item_id}/image?tag={image_tag}.
    item_id: str
    # "Tome 3 · CBZ", in French; the number of the volume (null without one) and its format
    # ("CBZ", "EPUB", "M4B") let a client write its own.
    label: str
    number: int | None
    format: str
    image_tag: str | None


class SourceCoverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    url: str


class SourceSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    text: str


class ProposedNameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    # "fr", "en", "ja-ro" (romaji), "ja"... or "latin" when the language is not known.
    language: str
    # The sources that gave it, the most trusted first, and the first of them.
    sources: list[SourceName]
    source: SourceName | None


class ProposedWorkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Its id in the work search; its cover at /works/cover?id={id} when `cover_url` is set.
    id: str
    title: str
    shelf_name: str
    authors: list[str]
    year: int | None
    sources: list[SourceName]
    cover_url: str | None


class ProposalsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    volumes: list[VolumeImageRead]
    covers: list[SourceCoverRead]
    summaries: list[SourceSummaryRead]
    work_id: str | None
    # The work the proposals come from: the one the series was linked to (`linked`), else the
    # first the sources find under its name; null without one.
    work: ProposedWorkRead | None
    linked: bool
    # The names of that work: the proposals of the title.
    names: list[ProposedNameRead]


class WorkLinkBody(BaseModel):
    # A work a search returned in the last days.
    work_id: str = Field(min_length=1, max_length=200)


class AdoptionFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    # Its file, as Jellyfin sees it, and its size (null when Jellyfin does not tell it).
    path: str
    size: int | None
    # The number proposed: a volume, or a chapter; none when nothing gives one.
    volume: int | None
    chapter: float | None
    # Where it comes from: `jellyfin` (its IndexNumber), `name` (its file name), or null.
    origin: NumberOrigin | None
    # The name it would take in its folder; null without a number.
    target: str | None
    # On the shelf already: it cannot be adopted again.
    adopted: bool


class AdoptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series_id: str
    # The work the files would belong to; null: no work, nothing can be adopted.
    work_id: str | None
    files: list[AdoptionFileRead]


class AdoptionChoiceBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    volume: int | None = Field(default=None, ge=0, le=9999)
    chapter: float | None = Field(default=None, ge=0, le=99999)
    include: bool = True


class AdoptionBody(BaseModel):
    items: list[AdoptionChoiceBody] = Field(min_length=1, max_length=2000)
    # Renamed to the names of the shelf by the placement worker, then recorded.
    place: bool = False


class AdoptionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adopted: int
    # Asked of the placement worker (`place`): it renames then records them at its next round.
    renamed: bool
    # The files whose name is taken in their folder: adopted under their name of before.
    conflicts: list[str]


class ImageBody(BaseModel):
    # "item": the image of a volume (item_id); "url": an image at an address (url); "data": an
    # image sent (data, in base64).
    kind: Literal["item", "url", "data"]
    item_id: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=2000, pattern=r"^https?://")
    data: str | None = Field(default=None, max_length=SENT_MAX)

    @field_validator("data")
    @classmethod
    def base64_of(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                base64.b64decode(value, validate=True)
            except binascii.Error as exc:
                raise ValueError("not base64") from exc
        return value


class SeriesChangeBody(BaseModel):
    name: ShortText = Field(min_length=1)
    original_title: ShortText = ""
    authors: list[ShortText] = Field(default=[], max_length=20)
    year: int | None = Field(default=None, ge=0, le=9999)
    genres: list[ShortText] = Field(default=[], max_length=30)
    summary: str = Field(default="", max_length=10000)
    # The fields changed locked in Jellyfin.
    lock: bool = True
    # The summary copied on the volumes without one.
    summary_to_volumes: bool = False
    image: ImageBody | None = None
    image_to_series: bool = True
    image_to_volumes: bool = False
    # The image written as the cover.jpg of the folder of the series (by the placement worker).
    save_cover: bool = False


class SummariesBody(BaseModel):
    # The summary of each series, by its id.
    summaries: dict[Annotated[str, StringConstraints(max_length=64)], str] = Field(max_length=500)


class FilledRead(BaseModel):
    series: int


class ScanBody(BaseModel):
    mode: ScanMode
    # A library of a kind, a series, or every library (both null).
    kind: Kind | None = None
    series_id: str | None = Field(default=None, max_length=64)


class ScanRead(BaseModel):
    # The progress of the scan of each library (0 to 100), null when idle.
    progress: dict[Kind, float | None]


class VolumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The id of its item in Jellyfin: its image at /library/items/{id}/image, its file at
    # /library/items/{id}/file.
    id: str
    # "Book" or "AudioBook".
    type: str
    name: str
    # Its number (IndexNumber), null without one.
    number: int | None
    summary: str
    authors: list[str]
    has_image: bool
    file_name: str
    # The size of its file in bytes, null when Jellyfin does not tell it.
    size: int | None
    # The tag of its image in Jellyfin, which changes with it (null without one).
    image_tag: str | None


class VolumesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series: SeriesRead
    volumes: list[VolumeRead]
    # The numbers between 1 and the highest held that no volume holds.
    missing: list[int]


class VolumeChangeBody(BaseModel):
    name: ShortText = Field(min_length=1)
    number: int | None = Field(default=None, ge=0, le=9999)
    summary: str = Field(default="", max_length=10000)
    authors: list[ShortText] = Field(default=[], max_length=20)
    # The fields changed locked in Jellyfin (Name, Overview, Cast).
    lock: bool = True
    image: ImageBody | None = None


class SyncBody(BaseModel):
    # A series, or every library (null).
    series_id: str | None = Field(default=None, max_length=64)


class SyncRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # "idle" (none since the start of the API), "running", "done", "failed".
    stage: SyncStage
    series_id: str | None
    # The items written again, those that held these metadata, the files placed that
    # Jellyfin does not list.
    changed: int
    unchanged: int
    not_found: int
    started_at: int | None
    ended_at: int | None
