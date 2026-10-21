"""Request and response schemas of the downloads module."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from shelfdrop.downloads.types import DownloadMode, Failure, Shown
from shelfdrop.works.types import Kind

type ShortText = Annotated[str, StringConstraints(max_length=200)]


class VolumesBody(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # "single" (first), "range" (first to last), "complete", "unknown".
    kind: Literal["single", "range", "complete", "unknown"]
    first: int | None = Field(default=None, ge=0, le=9999)
    last: int | None = Field(default=None, ge=0, le=9999)


class ReleaseChoice(BaseModel):
    # The id of a release of the search.
    id: str = Field(pattern=r"^[0-9a-f]{16}$")
    # Its volumes, as the page gives them.
    volumes: VolumesBody


class DownloadsCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "search_id": "3f2a9c1e0b7d4a58",
                    "work_id": "mangaupdates:57785063400",
                    "author": "Tatsuki Fujimoto",
                    "series": "Chainsaw Man",
                    "releases": [
                        {
                            "id": "0123456789abcdef",
                            "volumes": {"kind": "range", "first": 1, "last": 11},
                        }
                    ],
                }
            ]
        }
    )

    # The search the releases come from: a search of a work gives automatic downloads, a
    # manual search manual ones.
    search_id: str = Field(min_length=1, max_length=64)
    # The work (an id of the work search), the author and the series of the shelf; ignored for
    # a manual search.
    work_id: ShortText | None = None
    author: ShortText = ""
    series: ShortText = ""
    releases: list[ReleaseChoice] = Field(min_length=1, max_length=100)


class ProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # "downloading", "waiting" (being sent, or waiting in qBittorrent), "placing" (an automatic
    # download complete, being placed), "placed", "to_place" (a manual one complete, or one the
    # placement left to Ranger), "failed".
    state: Shown
    # While it downloads: from 0 to 100, bytes a second, seconds left (0 when unknown); while
    # its MP3 tracks are merged: the percent of the merge.
    percent: int | None
    speed: int | None
    eta: int | None
    # A failure: "not_received" (it may be sent again) or "duplicate".
    reason: Failure | None
    # Placed: where (the library, then the series).
    destination: str | None
    # To place: why ("manual", "chapters", "no_volume", "missing_files", "link_refused"...).
    unplaced: str | None


class DownloadRead(BaseModel):
    id: int
    # The release.
    title: str
    indexer: str
    size: int
    info_hash: str | None
    mode: DownloadMode
    kind: Kind
    # The category of qBittorrent.
    category: str
    work_id: str | None
    # The name of the work, or the text of a manual search.
    work_name: str
    author: str
    series: str
    volumes: VolumesBody
    progress: ProgressRead
    attempts: int
    # Unix seconds, and the account that asked.
    created_at: int
    created_by: str


class DownloadsRead(BaseModel):
    downloads: list[DownloadRead]
