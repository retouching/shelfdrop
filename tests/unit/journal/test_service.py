"""shelfdrop.journal.service: the events kept, then posted on Discord one message per batch,
after the window of the batch; a 429 waits, 3 failures drop the message."""

import itertools
from collections.abc import Sequence
from typing import override

import httpx
import pytest

from shelfdrop.clients.discord import DiscordClient
from shelfdrop.journal.repository import EventRepository
from shelfdrop.journal.service import Journal, JournalSender
from shelfdrop.journal.types import Event, EventState, JournalOptions, NewEvent
from tests.unit.clients.support import FakeDiscord
from tests.unit.support import no_session
from tests.unit.works.support import FixedClock

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32


class FakeEventRepository(EventRepository):
    """The events in memory; one instance plays every session."""

    def __init__(self) -> None:
        super().__init__(no_session())
        self.rows: dict[int, tuple[Event, EventState]] = {}
        self.ids = itertools.count(1)

    @override
    def add(self, event: NewEvent, now: int) -> None:
        new = Event(
            id=next(self.ids),
            type=event.type,
            group=event.group,
            facts=event.facts,
            cover=event.cover,
            created_at=now,
            attempts=0,
        )
        self.rows[new.id] = (new, "pending")

    @override
    def read_pending(self) -> list[Event]:
        return [event for event, state in self.rows.values() if state == "pending"]

    @override
    def mark(self, event_ids: Sequence[int], state: EventState, now: int | None = None) -> None:
        for i in event_ids:
            self.rows[i] = (self.rows[i][0], state)

    @override
    def count_attempt(self, event_ids: Sequence[int]) -> None:
        for i in event_ids:
            event, state = self.rows[i]
            self.rows[i] = (
                Event(**{**event.__dict__, "attempts": event.attempts + 1}),
                state,
            )

    @override
    def commit(self) -> None:
        pass

    @override
    def close(self) -> None:
        pass

    def states(self) -> list[EventState]:
        return [state for _, state in self.rows.values()]


class FakeDiscordSettings:
    def __init__(
        self, webhook: str | None = FakeDiscord.WEBHOOK, off: frozenset[str] = frozenset()
    ):
        self.webhook = webhook
        self.off = off

    async def discord(self) -> tuple[str | None, frozenset[str]]:
        events = {"sent", "placed", "login", "failed", "found"} - self.off
        return self.webhook, frozenset(events)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_journal(
    discord: FakeDiscord, settings: FakeDiscordSettings | None = None
) -> tuple[Journal, JournalSender, FakeEventRepository, FixedClock]:
    repository = FakeEventRepository()
    clock = FixedClock()
    client = DiscordClient(httpx.AsyncClient(transport=httpx.MockTransport(discord)))
    sender = JournalSender(
        client,
        settings or FakeDiscordSettings(),
        lambda: repository,
        JournalOptions(batch_seconds=30, every_seconds=0),
        clock,
        "https://shelfdrop.test",
    )
    return Journal(lambda: repository, clock), sender, repository, clock


def sent(volume: int, group: str = "sent:sylvain:1:Berserk") -> NewEvent:
    return NewEvent(type="sent", group=group, facts={"work": "Berserk", "volumes": [volume]})


@pytest.mark.anyio
async def test_a_batch_waits_its_window_then_goes_as_one_message() -> None:
    discord = FakeDiscord()
    journal, sender, repository, clock = new_journal(discord)
    journal.record(sent(1))
    clock.at += 10
    journal.record(sent(2))
    journal.record(sent(3, group="sent:sylvain:9:Gunnm"))

    assert await sender.post_ready() == 0
    clock.at += 25

    assert await sender.post_ready() == 1
    [(payload, picture)] = discord.messages
    [embed] = payload["embeds"]
    assert embed["title"] == "Envoyé : Berserk"
    assert embed["fields"][0]["value"] == "T01 à T02"
    assert picture is None
    assert repository.states() == ["sent", "sent", "pending"]


@pytest.mark.anyio
async def test_without_a_webhook_or_with_its_type_off_nothing_is_posted() -> None:
    discord = FakeDiscord()
    journal, sender, repository, clock = new_journal(
        discord, FakeDiscordSettings(off=frozenset({"login"}))
    )
    journal.record(NewEvent(type="login", group="login:a", facts={"account": "a"}))
    clock.at += 60

    await sender.post_ready()

    assert discord.messages == []
    assert repository.states() == ["skipped"]
    journal.record(sent(1))
    clock.at += 60
    sender.settings = FakeDiscordSettings(webhook=None)
    await sender.post_ready()
    assert repository.states() == ["skipped", "skipped"]


@pytest.mark.anyio
async def test_a_cover_is_joined_and_anything_else_is_not_kept() -> None:
    discord = FakeDiscord()
    journal, sender, _, clock = new_journal(discord)
    journal.record(NewEvent(type="placed", group="p", facts={"destination": "x"}, cover=JPEG))
    journal.record(NewEvent(type="placed", group="q", facts={"destination": "y"}, cover=b"<svg"))
    clock.at += 60

    await sender.post_ready()

    [(first, picture), (second, none)] = discord.messages
    assert picture == JPEG
    assert first["embeds"][0]["thumbnail"] == {"url": "attachment://cover.jpg"}
    assert none is None
    assert "thumbnail" not in second["embeds"][0]


@pytest.mark.anyio
async def test_a_429_keeps_the_batch_and_three_failures_drop_it() -> None:
    discord = FakeDiscord(limited=1)
    journal, sender, repository, clock = new_journal(discord)
    journal.record(sent(1))
    clock.at += 60

    assert await sender.post_ready() == 0
    assert repository.states() == ["pending"]
    discord.fails = 3
    for _ in range(3):
        await sender.post_ready()

    assert repository.states() == ["dropped"]
    assert discord.messages == []
