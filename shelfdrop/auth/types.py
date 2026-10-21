"""Types of the sign-in: an account signed in, a session opened, a session as it is kept."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Account:
    """An administrator of Jellyfin, signed in."""

    user_id: str
    username: str


@dataclass(frozen=True, kw_only=True)
class SignedIn:
    account: Account
    token: str
    """The token of the cookie: given once, never kept."""
    expires_at: int


@dataclass(frozen=True, kw_only=True)
class StoredSession:
    token_hash: str
    account: Account
    jellyfin_token: bytes
    """Sealed (ADR 0012)."""
    device_id: str
    created_at: int
    expires_at: int
    checked_at: int
