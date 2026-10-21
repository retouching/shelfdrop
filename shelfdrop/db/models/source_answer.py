"""SourceAnswer: what one metadata source answered to one search, kept for a day."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class SourceAnswer(Base):
    __tablename__ = "source_answers"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    # The family and the normalized search: "manga|chainsaw man".
    query: Mapped[str] = mapped_column(String(300), primary_key=True)
    # JSON list of the candidates the source gave.
    candidates: Mapped[str] = mapped_column(Text)
    # Unix seconds.
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
