"""Request and response schemas of the trackers module."""

from pydantic import BaseModel, ConfigDict, Field


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The id of the category in Prowlarr: a standard one under 100000, one of the indexer's own
    # from 100000.
    id: int
    # A sub-category carries the name of its parent ("Books/Comics").
    name: str


class KindCategories(BaseModel):
    """The categories searched for each kind; an empty list: the tracker is not asked for it."""

    manga: list[int] = Field(max_length=50)
    ebook: list[int] = Field(max_length=50)
    audiobook: list[int] = Field(max_length=50)


class TrackerRead(BaseModel):
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
    # The categories Prowlarr gave at its last read of the indexers.
    available_categories: list[CategoryRead]
    # The categories searched for each kind (the default ones until they are chosen).
    categories: KindCategories
    # Never chosen: the default ones, 7030 (manga), 7020 (ebook), 3030 (audiobook).
    default_categories: bool


class TrackersRead(BaseModel):
    # In their order: it breaks the ties between releases.
    trackers: list[TrackerRead]


class TrackerChoice(BaseModel):
    indexer_id: int
    used: bool
    auto: bool
    # Absent or null: the categories saved are kept.
    categories: KindCategories | None = None


class TrackersUpdate(BaseModel):
    # In the new order; a tracker left out keeps its choices and comes after.
    trackers: list[TrackerChoice] = Field(max_length=200)
