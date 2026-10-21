"""LibraryTask: a write in a library the API asks the placement worker for (the API never writes
there): the `cover.jpg` of a series."""

from sqlalchemy import Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class LibraryTask(Base):
    __tablename__ = "library_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # `cover`: `data` written as `cover.jpg` in the folder `path`, as Jellyfin sees it.
    kind: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(Text)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    # `pending`, `done` or `failed`; Unix seconds.
    state: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[int] = mapped_column(Integer)
    done_at: Mapped[int | None] = mapped_column(Integer)
