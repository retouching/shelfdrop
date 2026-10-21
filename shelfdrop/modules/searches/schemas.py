"""Request and response schemas of the searches module."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from shelfdrop.releases.types import NameState, Rejection, SearchMode, SearchState
from shelfdrop.works.types import Kind

type Name = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class SearchCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mode": "work",
                    "kind": "manga",
                    "title": "Chainsaw Man",
                    "names": ["Chainsaw Man", "Chensō Man"],
                    "refresh": False,
                },
                {
                    "mode": "manual",
                    "kind": "ebook",
                    "title": "Ne cède jamais",
                    "names": ["Ne cède jamais"],
                },
            ]
        }
    )

    # "work": the names of a work, the releases that miss a word of their name set aside;
    # "manual": one text, as typed.
    mode: SearchMode
    kind: Kind
    # What the search is shown as: the name of the work, or the text.
    title: str = Field(min_length=1, max_length=200)
    # The names searched; a manual search has one, a work 6 at most.
    names: list[Name] = Field(min_length=1, max_length=10)
    # Ask Prowlarr again instead of the answers kept 10 minutes.
    refresh: bool = False


class NameProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    state: NameState
    # Releases Prowlarr gave for this name, before any filter.
    found: int


class SearchProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mode: SearchMode
    kind: Kind
    title: str
    state: SearchState
    names: list[NameProgressRead]
    # Other searches with a name in the queue before this one.
    queued_ahead: int
    # Requests that asked this search; more than one: it is shared.
    followers: int
    # Unix seconds: when the oldest answer came from Prowlarr.
    fetched_at: float | None


class VolumesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: Literal["single", "range", "complete", "unknown"]
    first: int | None
    last: int | None


class RuleMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    score: int


class ReleaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    # The first name that found it.
    matched_name: str
    indexer_id: int
    indexer: str
    # Its place in the order of the trackers, 0 first.
    indexer_rank: int
    info_url: str | None
    info_hash: str | None
    seeders: int
    # Bytes.
    size: int
    volumes: VolumesRead
    score: int
    score_rules: list[RuleMatchRead]
    # Set aside: "relevance" (its title misses a word of its name) or "score" (under the
    # minimum); null when kept.
    rejected: Rejection | None
    # Kept, from a tracker allowed for the automatic downloads: a download of a work may take it.
    automatic: bool


class ReleaseSearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    progress: SearchProgressRead
    releases: list[ReleaseRead]
    minimum: int
