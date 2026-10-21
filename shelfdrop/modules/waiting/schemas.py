"""Request and response schemas of the waiting module."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from shelfdrop.waiting.types import Target, WaitingState
from shelfdrop.works.types import Kind

type ShortText = Annotated[str, StringConstraints(max_length=300)]


class WantedBody(BaseModel):
    # "any" release, a "volume", or "chapters" from chapter_from (to chapter_to, or every one
    # after when null).
    target: Target
    volume: int | None = Field(default=None, ge=0, le=9999)
    chapter_from: float | None = Field(default=None, ge=0, le=99999)
    chapter_to: float | None = Field(default=None, ge=0, le=99999)

    @model_validator(mode="after")
    def complete(self) -> "WantedBody":
        if self.target == "volume" and self.volume is None:
            raise ValueError("a volume needs its number")
        if self.target == "chapters" and (
            self.chapter_from is None
            or (self.chapter_to is not None and self.chapter_to < self.chapter_from)
        ):
            raise ValueError("chapters need their first, before their last")
        return self


class WaitingCreate(BaseModel):
    work_id: ShortText | None = None
    title: ShortText = Field(min_length=1)
    author: ShortText = ""
    kind: Kind
    # The names searched (those of the work, checked on the page).
    names: list[ShortText] = Field(min_length=1, max_length=10)
    wanted: list[WantedBody] = Field(min_length=1, max_length=200)


class WaitingRead(BaseModel):
    id: int
    work_id: str | None
    title: str
    author: str
    kind: Kind
    names: list[str]
    wanted: WantedBody
    # "T03", "Ch. 233 et suivants", "Toute release".
    label: str
    # "waiting" or "found" (releases: those of the last search that answer).
    state: WaitingState
    releases: int
    attempts: int
    created_at: int
    created_by: str
    searched_at: int | None
    next_search_at: int


class WaitingsRead(BaseModel):
    searches: list[WaitingRead]
    # Hours between two searches (the setting waiting.interval_hours).
    every_hours: int


class WaitingAdded(BaseModel):
    added: list[WaitingRead]
    # Those already waiting, not added again.
    skipped: int


class OwnedRead(BaseModel):
    # The volumes already placed or in the library.
    volumes: list[int]
