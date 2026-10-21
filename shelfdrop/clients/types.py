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
class TorrentInfo:
    """A torrent of qBittorrent (`GET /api/v2/torrents/info`)."""

    hash: str
    name: str
    state: str
    """`downloading`, `stalledDL`, `queuedDL`, `uploading`... (the WebUI API)."""
    progress: float
    """From 0 to 1."""
    speed: int
    """`dlspeed`, bytes a second."""
    eta: int
    """Seconds left; 8640000 when qBittorrent cannot tell."""
    category: str


@dataclass(frozen=True, kw_only=True)
class JellyfinLibrary:
    name: str
    collection_type: str | None
    """`books` for the libraries of books, comics and audiobooks."""
