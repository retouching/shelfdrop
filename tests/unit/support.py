"""Helpers shared by the unit tests."""

from typing import Any, cast

from sqlalchemy.orm import Session

from shelfdrop.journal.types import EventType, NewEvent


class NoSession:
    """A session no code may use: any access fails the test."""

    def __getattr__(self, name: str) -> Any:
        msg = f"the session must not be used (accessed {name})"
        raise AssertionError(msg)


def no_session() -> Session:
    # cast: the fake implements nothing; a fake repository built on it overrides every method.
    return cast("Session", NoSession())


class FakeJournal:
    """The journal of a test: the events recorded, in their order."""

    def __init__(self) -> None:
        self.events: list[NewEvent] = []

    def record(self, event: NewEvent) -> None:
        self.events.append(event)

    def of(self, event_type: EventType) -> list[NewEvent]:
        return [event for event in self.events if event.type == event_type]


type Bencodable = int | bytes | str | list["Bencodable"] | dict[str, "Bencodable"]


def bencode(value: Bencodable) -> bytes:
    """The bencoding of `value` (BEP 3), keys sorted: what a `.torrent` file holds."""
    match value:
        case int():
            return b"i%de" % value
        case str():
            return bencode(value.encode())
        case bytes():
            return b"%d:%s" % (len(value), value)
        case list():
            return b"l" + b"".join(bencode(item) for item in value) + b"e"
        case dict():
            items = sorted(value.items())
            return b"d" + b"".join(bencode(k) + bencode(v) for k, v in items) + b"e"


def torrent_file(name: str, *, size: int = 1024, v2: bool = False) -> bytes:
    """A `.torrent` file of one file named `name`, announced on a tracker with a passkey;
    `v2`: a hybrid torrent of BitTorrent v1 and v2."""
    info: dict[str, Bencodable] = {
        "name": name,
        "length": size,
        "piece length": 16384,
        "pieces": b"\x01" * 20,
    }
    if v2:
        info["meta version"] = 2
        info["file tree"] = {name: {"": {"length": size, "pieces root": b"\x02" * 32}}}
    return bencode(
        {"announce": "https://tracker.example/announce/passkey-of-the-tests", "info": info}
    )
