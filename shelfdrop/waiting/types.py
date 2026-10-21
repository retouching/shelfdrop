"""The searches kept waiting (plan section 3, point 11)."""

from dataclasses import dataclass
from typing import Literal

from shelfdrop.works.types import Kind

type Target = Literal["any", "volume", "chapters"]
type WaitingState = Literal["waiting", "found"]


@dataclass(frozen=True, kw_only=True)
class Wanted:
    """What a waiting search waits for: any release, a volume, or chapters from `chapter_from`
    to `chapter_to` (every one after when None)."""

    target: Target
    volume: int | None = None
    chapter_from: float | None = None
    chapter_to: float | None = None


@dataclass(frozen=True, kw_only=True)
class WaitOrder:
    """Searches to keep waiting for a work: one for each volume, chapters, or any release."""

    work_id: str | None
    title: str
    author: str
    kind: Kind
    names: tuple[str, ...]
    wanted: tuple[Wanted, ...]
    created_by: str


@dataclass(frozen=True, kw_only=True)
class Waiting:
    id: int
    work_id: str | None
    title: str
    author: str
    kind: Kind
    names: tuple[str, ...]
    wanted: Wanted
    state: WaitingState
    releases: int
    attempts: int
    created_at: int
    created_by: str
    searched_at: int | None


@dataclass(frozen=True, kw_only=True)
class WaitingView:
    """A waiting search, and when it is searched again."""

    waiting: Waiting
    next_search_at: int


@dataclass(frozen=True, kw_only=True)
class WaitingOptions:
    every_seconds: float = 60.0
    """Seconds between two rounds: each searches those due."""
