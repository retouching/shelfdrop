"""WaitingSearch: a search kept waiting, searched again at an interval until it finds a release,
and left once what it waits for is placed."""

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class WaitingSearch(Base):
    __tablename__ = "waiting_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The work (an id of the work search, None without one), its name on the shelf, its author,
    # its kind, and the names searched (JSON).
    work_id: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    author: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(10))
    names: Mapped[str] = mapped_column(Text)
    # What it waits for: `any` release, a `volume`, or `chapters` from `chapter_from` (to
    # `chapter_to`, or every one after when None).
    target: Mapped[str] = mapped_column(String(10))
    volume: Mapped[int | None] = mapped_column(Integer)
    chapter_from: Mapped[float | None] = mapped_column(Float)
    chapter_to: Mapped[float | None] = mapped_column(Float)
    # `waiting` or `found`, and the releases of its last search.
    state: Mapped[str] = mapped_column(String(10))
    releases: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer)
    # Unix seconds; `done_at`: what it waited for was placed, it left the list.
    created_at: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(200))
    searched_at: Mapped[int | None] = mapped_column(Integer)
    done_at: Mapped[int | None] = mapped_column(Integer, index=True)
