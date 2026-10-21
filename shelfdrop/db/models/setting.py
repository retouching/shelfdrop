"""Setting: one setting changed from the page, by its key."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class Setting(Base):
    __tablename__ = "settings"

    # "filters.minimum", "prowlarr.url"...
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    # JSON value.
    value: Mapped[str] = mapped_column(Text)
    # Unix seconds.
    updated_at: Mapped[int] = mapped_column(Integer)
    # The account that changed it, "environment" for an imported value; None before it was kept.
    updated_by: Mapped[str | None] = mapped_column(String(255))
