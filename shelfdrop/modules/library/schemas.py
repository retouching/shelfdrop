"""Request and response schemas of the library module (the page Métadonnées)."""

import base64
import binascii
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from shelfdrop.library.types import ScanMode
from shelfdrop.works.types import Kind

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


class LibraryRead(BaseModel):
    series: list[SeriesRead]


class VolumeImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The image is at /library/items/{item_id}/image.
    item_id: str
    label: str


class SourceCoverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    url: str


class SourceSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    text: str


class ProposalsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    volumes: list[VolumeImageRead]
    covers: list[SourceCoverRead]
    summaries: list[SourceSummaryRead]
    work_id: str | None


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
