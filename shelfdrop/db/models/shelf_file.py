"""ShelfFile: a file put on the shelf by the placement, and whether Jellyfin holds its metadata
locked."""

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class ShelfFile(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The download it comes from (None for a file placed by hand).
    download_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # What it is: the kind, the work (its id in the work search), the series and the author of
    # the shelf, its volume or its chapter.
    kind: Mapped[str] = mapped_column(String(10))
    work_id: Mapped[str | None] = mapped_column(String(200), index=True)
    series: Mapped[str] = mapped_column(String(200), index=True)
    author: Mapped[str] = mapped_column(String(200))
    volume: Mapped[int | None] = mapped_column(Integer)
    chapter: Mapped[float | None] = mapped_column(Float)
    # Where it is, as the placement sees it (/data/files/...).
    path: Mapped[str] = mapped_column(Text)
    # Its name, its series, its number and its authors set and locked in Jellyfin.
    locked: Mapped[bool] = mapped_column(Boolean)
    # Unix seconds.
    created_at: Mapped[int] = mapped_column(Integer)
