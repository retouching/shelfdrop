"""ApiToken: an access token of the API and of the MCP server, by the fingerprint of its
secret (ADR 0020)."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # The name given at its creation ("Agent"): the author of what it does.
    name: Mapped[str] = mapped_column(String(100))
    # The SHA-256 of the secret, in hex; the secret itself is shown once and never kept.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # "read" or "write" (shelfdrop.tokens.types.Scope).
    scope: Mapped[str] = mapped_column(String(10))
    # The account that created it.
    created_by: Mapped[str] = mapped_column(String(255))
    # Unix seconds; expires_at is None for a token without expiry, revoked_at None until it
    # is revoked, last_used_at None until its first use.
    created_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int | None] = mapped_column(Integer)
    last_used_at: Mapped[int | None] = mapped_column(Integer)
    revoked_at: Mapped[int | None] = mapped_column(Integer, index=True)
