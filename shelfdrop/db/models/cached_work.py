"""CachedWork: a merged work a search returned, kept a week so that its id can be read again."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class CachedWork(Base):
    __tablename__ = "cached_works"

    # The id of the work, "<source>:<id at that source>" of its first member.
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    # JSON of the work.
    work: Mapped[str] = mapped_column(Text)
    # Unix seconds.
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
