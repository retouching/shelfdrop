"""Types of the sign-in: an account signed in, a session opened, a session as it is kept."""

from dataclasses import dataclass
from typing import Final

# The id of the internal account of shelfdrop in a session; an account of Jellyfin has its id
# there, an access token `token:<id>`.
INTERNAL_USER_ID: Final = "internal"


@dataclass(frozen=True, kw_only=True)
class Account:
    """The internal account or an administrator of Jellyfin, signed in (or an access token,
    the author of what it does)."""

    user_id: str
    username: str

    @property
    def internal(self) -> bool:
        return self.user_id == INTERNAL_USER_ID


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
    """Sealed (ADR 0012); empty for the internal account."""
    device_id: str
    """Empty for the internal account."""
    created_at: int
    expires_at: int
    checked_at: int
