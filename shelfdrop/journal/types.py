"""Types of the journal: an event of shelfdrop, kept, then posted on Discord."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

type EventType = Literal[
    "sent",
    "downloaded",
    "placed",
    "to_place",
    "uploaded",
    "retry",
    "failed",
    "misplaced",
    "login",
    "found",
]
type EventState = Literal["pending", "sent", "skipped", "dropped"]
type Fact = str | int | float | bool | list[int] | list[str] | None

# The color of the embed of each type: the Radix palette of the pages.
COLORS: Final[Mapping[EventType, int]] = {
    "sent": 0x6E56CF,
    "downloaded": 0x7CE2FE,
    "placed": 0x30A46C,
    "to_place": 0xFFC53D,
    "uploaded": 0xAB4ABA,
    "retry": 0xF76B15,
    "failed": 0xE5484D,
    "misplaced": 0x8E8C99,
    "login": 0xD6409F,
    "found": 0x12A594,
}


@dataclass(frozen=True, kw_only=True)
class NewEvent:
    """An event to post. The events of one `group` and one type within the batch window make
    one message (22 volumes sent: one message, not 22)."""

    type: EventType
    group: str
    facts: Mapping[str, Fact] = field(default_factory=dict)
    """What the message says, by name: `work`, `volumes`, `size`... (`shelfdrop.journal.embeds`)."""
    cover: bytes | None = None
    """A picture joined to the message (the cover of a volume placed): JPEG, PNG or WebP, kept
    with the event, since the process that posts it may not see the library."""


@dataclass(frozen=True, kw_only=True)
class Event:
    id: int
    type: EventType
    group: str
    facts: Mapping[str, Fact]
    cover: bytes | None
    created_at: int
    attempts: int


@dataclass(frozen=True, kw_only=True)
class JournalOptions:
    # The events of one group wait this long for the others of their batch.
    batch_seconds: int = 30
    # Seconds between two looks for the events to post.
    every_seconds: float = 5.0
    # A message that fails this many times is dropped (and logged).
    tries: int = 3
    # Messages posted at most in one look: Discord takes 30 a minute on a webhook.
    per_round: int = 5
