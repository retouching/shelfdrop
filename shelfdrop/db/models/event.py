"""Event: an event of the journal, posted on Discord with the others of its batch."""

from sqlalchemy import Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Its type (`sent`, `placed`...), and its batch: the events of one group and one type make
    # one message.
    type: Mapped[str] = mapped_column(String(20))
    group_key: Mapped[str] = mapped_column(String(300))
    # What the message says, as JSON (shelfdrop.journal.types.NewEvent.facts), and a picture
    # joined to it (JPEG, PNG or WebP).
    facts: Mapped[str] = mapped_column(Text)
    cover: Mapped[bytes | None] = mapped_column(LargeBinary)
    # `pending`, `sent`, `skipped` (no webhook, or its type switched off) or `dropped` (failed
    # 3 times), and the attempts of its message.
    state: Mapped[str] = mapped_column(String(10), index=True)
    attempts: Mapped[int] = mapped_column(Integer)
    # Unix seconds.
    created_at: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[int | None] = mapped_column(Integer)
