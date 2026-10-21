"""Request and response schemas of the trackers module."""

from pydantic import BaseModel, ConfigDict, Field


class TrackerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The id of the indexer in Prowlarr.
    indexer_id: int
    name: str
    # As Prowlarr gives it ("fr-FR"), or null.
    language: str | None
    # Off in Prowlarr: listed apart, never asked.
    prowlarr_enabled: bool
    # Asked by the searches.
    used: bool
    # Allowed for the automatic downloads.
    auto: bool


class TrackersRead(BaseModel):
    # In their order: it breaks the ties between releases.
    trackers: list[TrackerRead]


class TrackerChoice(BaseModel):
    indexer_id: int
    used: bool
    auto: bool


class TrackersUpdate(BaseModel):
    # In the new order; a tracker left out keeps its choices and comes after.
    trackers: list[TrackerChoice] = Field(max_length=200)
