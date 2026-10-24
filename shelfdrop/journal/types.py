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


@dataclass(frozen=True, kw_only=True)
class JournalTexts:
    """The texts of the messages in one language (`shelfdrop.journal.texts`). A format takes its
    values by position (`volume`: the number) or by name (`hours`: `hours` and `minutes`)."""

    titles: Mapping[EventType, str]
    # Between the title of a type and its subject: "Envoyé : Berserk", "Sent: Berserk".
    separator: str
    volumes: str
    already: str
    trackers: str
    size: str
    type: str
    mode: str
    modes: Mapping[str, str]
    by: str
    duration: str
    reason: str
    attempt: str
    result: str
    # `{client}`: the name of the torrent client.
    results: Mapping[str, str]
    error: str
    done: str
    country: str
    refused: str
    releases: str
    place: str
    # Why a download was not placed alone: the page Ranger takes it.
    reasons: Mapping[str, str]
    # What failed, and what shelfdrop did then (`{client}`: the name of the torrent client).
    failures: Mapping[str, str]
    actions: Mapping[str, str]
    # A volume, a run of volumes, and the word before the last run of a list.
    volume: str
    volume_range: str
    last_join: str
    gigabytes: str
    megabytes: str
    decimal: str
    seconds: str
    minutes: str
    hours: str
    # What a waiting search found (`found`): any release, chapters from one, chapters a to b.
    any_release: str
    chapters_from: str
    chapters_range: str
