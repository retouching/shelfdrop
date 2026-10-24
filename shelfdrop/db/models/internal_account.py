"""InternalAccount: the account of shelfdrop itself, its one administrator: it signs in without
Jellyfin, and its creation opens the set-up of the first launch."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class InternalAccount(Base):
    __tablename__ = "internal_account"

    # Always 1: one account at most, and the second creation fails on the key.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    username: Mapped[str] = mapped_column(String(64))
    # scrypt, its parameters and its salt with it (shelfdrop.utils.passwords).
    password_hash: Mapped[str] = mapped_column(String(255))
    # Unix seconds; setup_finished_at is None while the set-up of the first launch is not
    # finished.
    created_at: Mapped[int] = mapped_column(Integer)
    password_changed_at: Mapped[int] = mapped_column(Integer)
    setup_finished_at: Mapped[int | None] = mapped_column(Integer)
