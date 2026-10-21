"""LoginSession: the session of an account signed in, by the fingerprint of its token."""

from sqlalchemy import Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class LoginSession(Base):
    __tablename__ = "sessions"

    # The SHA-256 of the token of the cookie, in hex; the token itself is never kept.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    # The account in Jellyfin: its id and its name.
    user_id: Mapped[str] = mapped_column(String(64))
    username: Mapped[str] = mapped_column(String(255))
    # The access token Jellyfin gave at sign-in, sealed (ADR 0012), and the device it names:
    # the session is checked again with them.
    jellyfin_token: Mapped[bytes] = mapped_column(LargeBinary)
    device_id: Mapped[str] = mapped_column(String(64))
    # Unix seconds.
    created_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    # When Jellyfin last confirmed the account is still an administrator.
    checked_at: Mapped[int] = mapped_column(Integer)
