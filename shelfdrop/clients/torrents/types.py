"""What shelfdrop reads from a torrent client, whatever the client: a torrent, and the test of a
connection."""

from dataclasses import dataclass
from typing import Literal

type TorrentStatus = Literal["waiting", "downloading", "stalled", "complete", "error"]
"""`waiting`: queued, paused, checked, fetching its metadata, moved...; `downloading`; `stalled`:
it tries to download, with no peer; `complete`: the client has all of it (seeding or not);
`error`: the client stopped on an error (files missing, a disk full...)."""


@dataclass(frozen=True, kw_only=True)
class TorrentInfo:
    """A torrent of the client, the same for every client."""

    hash: str
    """Its info hash, in lowercase hex (40 characters)."""
    name: str
    status: TorrentStatus
    progress: float
    """From 0 to 1."""
    speed: int
    """Bytes a second it downloads."""
    eta: int | None
    """Seconds left; None when the client cannot tell."""
    category: str
    """Its category (qBittorrent) or its label (Deluge, Transmission)."""
    content_path: str = ""
    """Where the client keeps it, as the client sees it: the file of a single-file torrent, its
    folder otherwise; "" when the client gives none."""
    placed: bool = False
    """It carries the mark of shelfdrop on what it placed (`mark_placed`)."""


@dataclass(frozen=True, kw_only=True)
class TorrentCheck:
    """The test of a connection: the client answered, and what it misses for shelfdrop."""

    version: str
    """The version of the client (`5.1.2`)."""
    missing: tuple[str, ...] = ()
    """The categories (or labels) asked for that the client does not have."""
    unsupported: str | None = None
    """Why shelfdrop cannot send to this client, None when it can: a feature it lacks (a plugin
    off, a version too old), named by the connector."""
