"""FilterRule: a rule of the filters of the releases, in its order."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class FilterRule(Base):
    __tablename__ = "filter_rules"

    position: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(100))
    # Comma-separated words, or a regular expression when `regex`.
    pattern: Mapped[str] = mapped_column(String(500))
    regex: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[int] = mapped_column(Integer)
    # The kinds it applies to, comma-separated; empty: every kind.
    kinds: Mapped[str] = mapped_column(String(40))
    enabled: Mapped[bool] = mapped_column(Boolean)
