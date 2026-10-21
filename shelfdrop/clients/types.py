"""What the clients of the services read from them."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class JellyfinUser:
    id: str
    name: str
    administrator: bool
    """`Policy.IsAdministrator`."""
    disabled: bool
    """`Policy.IsDisabled`."""


@dataclass(frozen=True, kw_only=True)
class JellyfinLogin:
    user: JellyfinUser
    token: str
    """The access token of the session Jellyfin opened."""


@dataclass(frozen=True, kw_only=True)
class JellyfinLibrary:
    name: str
    collection_type: str | None
    """`books` for the libraries of books, comics and audiobooks."""
