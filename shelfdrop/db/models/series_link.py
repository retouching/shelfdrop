"""SeriesLink: the work a series of Jellyfin was linked to by hand, from the page Jellyfin."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class SeriesLink(Base):
    __tablename__ = "series_links"

    # The id of the folder of the series in Jellyfin.
    series_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    # Its id in the work search, and its name, to search it again once its cache expired.
    work_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    # Unix seconds.
    updated_at: Mapped[int] = mapped_column(Integer)
