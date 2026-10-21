"""ReleaseAnswer: what Prowlarr answered to one name, kept 10 minutes."""

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class ReleaseAnswer(Base):
    __tablename__ = "release_answers"

    # The normalized name, the categories and the indexers asked: "chainsaw man|7030|1,2".
    key: Mapped[str] = mapped_column(String(400), primary_key=True)
    # JSON list of the releases found.
    releases: Mapped[str] = mapped_column(Text)
    # Unix seconds: when Prowlarr answered, and when the answer is no longer used.
    fetched_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
