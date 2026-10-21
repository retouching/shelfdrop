"""PlaceItem: a file (or a folder of files) of the page Ranger, to place by hand: a download the
worker did not place alone, or a file of the libraries the scan found misplaced."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class PlaceItem(Base):
    __tablename__ = "place_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Where it comes from: a `download` (its files stay, hardlinked), the `library` (moved);
    # the download it is part of.
    origin: Mapped[str] = mapped_column(String(10))
    download_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # Its kind when known, its name on the page, its path as the worker sees it (a file or a
    # folder), its files (JSON, the paths of the worker), their size.
    kind: Mapped[str | None] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(300))
    path: Mapped[str] = mapped_column(Text, index=True)
    files: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer)
    # `unlinked` (to link to a work), `chapters` (a release in chapters, to link to volumes),
    # `misplaced` (found by the scan) or `placed`; why (`chapters`, `manual`, `root`...).
    state: Mapped[str] = mapped_column(String(10), index=True)
    reason: Mapped[str | None] = mapped_column(String(20))
    # The chapters of its files (JSON), the series its name or its download gives, the volumes
    # of that series on the shelf (JSON), its work and author as its download gave them.
    chapters: Mapped[str] = mapped_column(Text)
    series: Mapped[str] = mapped_column(String(200))
    existing: Mapped[str] = mapped_column(Text)
    # The chapters loose in the folder of that series, out of its files (JSON): with its own,
    # they make a volume complete; the worker reads them again at each round.
    loose: Mapped[str] = mapped_column(Text, server_default="[]")
    work_id: Mapped[str | None] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(200))
    # What the page asked (JSON, `shelfdrop.placement.types.PlaceRequest`) until the worker
    # does it; the reason the last one failed; where it went.
    request: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(String(20))
    destination: Mapped[str | None] = mapped_column(String(300))
    # Unix seconds.
    created_at: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[int] = mapped_column(Integer)
