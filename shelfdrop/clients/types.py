"""What the clients of the services read from them."""

from collections.abc import AsyncIterator, Awaitable, Callable
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
    content_path: str = ""
    """Where qBittorrent keeps it, as qBittorrent sees it: the file of a single-file torrent,
    its folder otherwise."""


@dataclass(frozen=True, kw_only=True)
class JellyfinLibrary:
    name: str
    collection_type: str | None
    """`books` for the libraries of books, comics and audiobooks."""
    item_id: str | None = None
    locations: tuple[str, ...] = ()
    """Its folders, as Jellyfin sees them."""
    refresh_progress: float | None = None
    """The scan running, from 0 to 100; None when it is idle."""


@dataclass(frozen=True, kw_only=True)
class JellyfinItem:
    """An item of `GET /Items`: a book, an audiobook or a folder of a library."""

    id: str
    type: str
    name: str
    path: str
    overview: str
    genres: tuple[str, ...]
    authors: tuple[str, ...]
    """The people of type `Author`."""
    year: int | None
    original_title: str
    has_image: bool
    """Its `Primary` image."""
    index_number: int | None


@dataclass(frozen=True, kw_only=True)
class JellyfinFile:
    """The file of an item, read from `GET /Items/{id}/Download` as it comes."""

    content_type: str
    size: int | None
    """Its `Content-Length`, None without one."""
    chunks: AsyncIterator[bytes]
    """Its bytes; raises ServiceError when Jellyfin stops sending them."""
    close: Callable[[], Awaitable[None]]
    """Closes the answer of Jellyfin (the end of `chunks` closes it too)."""
