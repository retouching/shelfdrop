"""The journal: the events of shelfdrop kept as they happen (`Journal`), then posted on the
Discord webhook by `JournalSender`, one message per batch.

Every process writes its events (the API, the placement worker); the API alone posts them. A
message that fails 3 times is dropped and logged: the journal never holds up a download nor a
placement.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from typing import Final, Protocol

import anyio
import anyio.to_thread

from shelfdrop.clients.discord import DiscordClient, RateLimitedError
from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.journal.embeds import embed_of
from shelfdrop.journal.repository import EventRepository, EventRepositoryFactory
from shelfdrop.journal.types import Event, EventState, JournalOptions, NewEvent
from shelfdrop.utils.pictures import picture_of
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)

# A picture over this size is not kept (Discord takes 10 MB a message without Nitro).
COVER_MAX_BYTES: Final = 8 * 1024 * 1024


class DiscordSettings(Protocol):
    """The webhook of the journal and the events switched on, read at each look (the
    settings)."""

    async def discord(self) -> tuple[str | None, frozenset[str]]: ...


class Journal:
    """Keeps the events: each on a session of its own, called from the threadpool."""

    def __init__(self, repositories: EventRepositoryFactory, clock: Clock) -> None:
        self.repositories = repositories
        self.clock = clock

    def record(self, event: NewEvent) -> None:
        if event.cover is not None and (
            len(event.cover) > COVER_MAX_BYTES or picture_of(event.cover) is None
        ):
            event = NewEvent(type=event.type, group=event.group, facts=event.facts)
        repository = self.repositories()
        try:
            repository.add(event, int(self.clock.now()))
            repository.commit()
        except Exception:
            # The journal never holds up what it reports.
            logger.exception("Event not kept", extra={"type": event.type})
        finally:
            repository.close()


def batches(events: Sequence[Event]) -> list[list[Event]]:
    """The events by type and group, in the order of their first event."""
    found: dict[tuple[str, str], list[Event]] = {}
    for event in events:
        found.setdefault((event.type, event.group), []).append(event)
    return list(found.values())


def cover_of(events: Sequence[Event]) -> tuple[str, bytes, str] | None:
    """The first picture of the batch: its name in the message, its bytes, its type."""
    for event in events:
        found = None if event.cover is None else picture_of(event.cover)
        if event.cover is not None and found is not None:
            extension, content_type = found
            return f"cover.{extension}", event.cover, content_type
    return None


class JournalSender:
    """Posts the batches whose first event is `batch_seconds` old, every `every_seconds` (a
    container singleton, run by the lifespan of the API)."""

    def __init__(
        self,
        discord: DiscordClient,
        settings: DiscordSettings,
        repositories: EventRepositoryFactory,
        options: JournalOptions,
        clock: Clock,
        public_url: str | None,
    ) -> None:
        self.discord = discord
        self.settings = settings
        self.repositories = repositories
        self.options = options
        self.clock = clock
        self.public_url = public_url

    async def run(self) -> None:
        """Until cancelled."""
        while True:
            try:
                await self.post_ready()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Journal round failed")
            await anyio.sleep(self.options.every_seconds)

    async def post_ready(self) -> int:
        """Posts the batches ready, `per_round` at most; returns how many were posted."""
        pending = await self.use(lambda r: r.read_pending(), commit=False)
        now = int(self.clock.now())
        ready = [
            batch
            for batch in batches(pending)
            if now - batch[0].created_at >= self.options.batch_seconds
        ]
        if not ready:
            return 0
        webhook, enabled = await self.settings.discord()
        posted = 0
        for batch in ready:
            ids = [e.id for e in batch]
            if not webhook or batch[0].type not in enabled:
                await self.mark(ids, "skipped", None)
                continue
            if posted >= self.options.per_round:
                break
            cover = cover_of(batch)
            embed = embed_of(batch, self.public_url, None if cover is None else cover[0])
            try:
                await self.discord.post(webhook, {"embeds": [embed]}, cover)
            except RateLimitedError as exc:
                logger.info("Discord asks to wait", extra={"seconds": exc.retry_after})
                await anyio.sleep(min(exc.retry_after, 60.0))
                break
            except ServiceError as exc:
                await self.failed(batch, type(exc).__name__)
                continue
            posted += 1
            await self.mark(ids, "sent", int(self.clock.now()))
        return posted

    async def mark(self, ids: Sequence[int], state: EventState, now: int | None) -> None:
        await self.use(lambda r: r.mark(ids, state, now))

    async def failed(self, batch: Sequence[Event], error: str) -> None:
        ids = [e.id for e in batch]
        attempts = max(e.attempts for e in batch) + 1
        if attempts >= self.options.tries:
            logger.warning(
                "Discord message dropped",
                extra={"type": batch[0].type, "events": len(ids), "error": error},
            )
            await self.mark(ids, "dropped", None)
        else:
            await self.use(lambda r: r.count_attempt(ids))

    def run_on[T](self, action: Callable[[EventRepository], T], commit: bool) -> T:
        repository = self.repositories()
        try:
            result = action(repository)
            if commit:
                repository.commit()
            return result
        finally:
            repository.close()

    async def use[T](self, action: Callable[[EventRepository], T], *, commit: bool = True) -> T:
        return await anyio.to_thread.run_sync(self.run_on, action, commit)
