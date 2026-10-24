"""WorkMerge: works the page joined by hand into one, applied to every
search after."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class WorkMerge(Base):
    __tablename__ = "work_merges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The family of the searches it applies to: `manga` or `book`.
    family: Mapped[str] = mapped_column(String(10), index=True)
    # The keys of the members of the works joined (JSON, `<source>:<id at that source>`).
    keys: Mapped[str] = mapped_column(Text)
    # The name on the shelf chosen for the work they make.
    shelf_name: Mapped[str] = mapped_column(String(300))
    # Unix seconds.
    created_at: Mapped[int] = mapped_column(Integer)
