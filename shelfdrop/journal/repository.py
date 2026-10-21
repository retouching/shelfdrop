"""EventRepository: the events of the journal and the state of their messages."""

import json
from collections.abc import Callable, Sequence
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from shelfdrop.db.models import Event as EventRow
from shelfdrop.journal.types import Event, EventState, EventType, Fact, NewEvent

EVENT_TYPE: Final = TypeAdapter[EventType](EventType)
FACTS: Final = TypeAdapter[dict[str, Fact]](dict[str, Fact])


def event_of(row: EventRow) -> Event:
    return Event(
        id=row.id,
        type=EVENT_TYPE.validate_python(row.type),
        group=row.group_key,
        facts=FACTS.validate_json(row.facts),
        cover=row.cover,
        created_at=row.created_at,
        attempts=row.attempts,
    )


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: NewEvent, now: int) -> None:
        self.session.add(
            EventRow(
                type=event.type,
                group_key=event.group[:300],
                facts=json.dumps(dict(event.facts), ensure_ascii=False),
                cover=event.cover,
                state="pending",
                attempts=0,
                created_at=now,
            )
        )

    def read_pending(self) -> list[Event]:
        """The events waiting for their message, the oldest first."""
        rows = self.session.scalars(
            select(EventRow).where(EventRow.state == "pending").order_by(EventRow.id)
        )
        return [event_of(row) for row in rows]

    def mark(self, event_ids: Sequence[int], state: EventState, now: int | None = None) -> None:
        self.session.execute(
            update(EventRow).where(EventRow.id.in_(event_ids)).values(state=state, sent_at=now)
        )

    def count_attempt(self, event_ids: Sequence[int]) -> None:
        self.session.execute(
            update(EventRow)
            .where(EventRow.id.in_(event_ids))
            .values(attempts=EventRow.attempts + 1)
        )

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type EventRepositoryFactory = Callable[[], EventRepository]


def event_repository_factory(engine: Engine) -> EventRepositoryFactory:
    def new() -> EventRepository:
        return EventRepository(Session(engine, expire_on_commit=False))

    return new
