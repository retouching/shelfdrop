"""Upload: a file sent from the page Manuel in chunks, kept until the
placement worker lists it in Ranger."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Its name (a file name alone), its size in bytes, the size of its chunks.
    name: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer)
    chunk_size: Mapped[int] = mapped_column(Integer)
    # The indexes of the chunks received (JSON), and its SHA-256 once checked.
    received: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    # `receiving`, `verified` (whole, its SHA-256 the one the page gave), `listed` (moved into
    # Ranger by the worker), `corrupt` or `lost` (its file gone before the worker took it).
    state: Mapped[str] = mapped_column(String(10), index=True)
    # Unix seconds.
    created_at: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[int] = mapped_column(Integer)
