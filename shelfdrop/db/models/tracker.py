"""Tracker: an indexer read from Prowlarr, whether shelfdrop asks it, and its place."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class Tracker(Base):
    __tablename__ = "trackers"

    # The id of the indexer in Prowlarr.
    indexer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))
    language: Mapped[str | None] = mapped_column(String(20))
    prowlarr_enabled: Mapped[bool] = mapped_column(Boolean)
    used: Mapped[bool] = mapped_column(Boolean)
    auto: Mapped[bool] = mapped_column(Boolean)
    # 0 first: the order of the trackers breaks the ties between releases.
    position: Mapped[int] = mapped_column(Integer)
