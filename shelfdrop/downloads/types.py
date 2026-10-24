"""Types of the downloads: a release sent to qBittorrent, its stage, and what the page shows of
it."""

from dataclasses import dataclass
from typing import Final, Literal

from shelfdrop.releases.types import Volumes
from shelfdrop.works.types import Kind

type DownloadMode = Literal["auto", "manual"]
type Stage = Literal["sending", "sent", "completed", "placed", "unplaced", "failed"]
type Failure = Literal["not_received", "duplicate"]
type Shown = Literal["downloading", "waiting", "placing", "placed", "to_place", "failed"]

# The categories of qBittorrent shelfdrop downloads into: one per kind, and one for the manual
# downloads, placed by hand.
CATEGORIES: Final[dict[Kind, str]] = {"manga": "manga", "ebook": "ebook", "audiobook": "audiobook"}
MANUAL_CATEGORY: Final = "shelfdrop-manual"


@dataclass(frozen=True, kw_only=True)
class NewDownload:
    """A release to send: what it is for, and who asked."""

    release_id: str
    guid: str
    title: str
    indexer_id: int
    indexer: str
    size: int
    download_url: str
    work_id: str | None
    work_name: str
    author: str
    series: str
    volumes: Volumes
    kind: Kind
    mode: DownloadMode
    category: str
    created_at: int
    created_by: str


@dataclass(frozen=True, kw_only=True)
class Download:
    """A release sent, or being sent, to qBittorrent."""

    id: int
    info_hash: str | None
    release_id: str
    title: str
    indexer: str
    size: int
    download_url: str | None
    work_id: str | None
    work_name: str
    author: str
    series: str
    volumes: Volumes
    kind: Kind
    mode: DownloadMode
    category: str
    stage: Stage
    """`sending`: being fetched, added and looked for; `sent`: found in qBittorrent by its hash;
    `completed`: qBittorrent has it all; `placed`: on the shelf; `unplaced`: to place in
    Ranger; `failed`: see `failure`."""
    failure: Failure | None
    attempts: int
    created_at: int
    created_by: str
    added_at: int | None
    """The first time qBittorrent took it: found there after, it is this download, not a
    duplicate."""
    completed_at: int | None = None
    destination: str | None = None
    """Where its placement put it: the name of its library, then its series."""
    unplaced: str | None = None
    """Why it was not placed alone (`shelfdrop.placement.types.Unplaced`)."""
    placing_percent: int | None = None
    """The merge of its MP3 tracks, while it runs."""
    copied: bool = False
    """A file of it copied on the shelf rather than hardlinked (`placement.mode`)."""


@dataclass(frozen=True, kw_only=True)
class Progress:
    """What the page shows of a download: its state, and, while it downloads, the figures of
    qBittorrent."""

    state: Shown
    percent: int | None = None
    speed: int | None = None
    """Bytes a second."""
    eta: int | None = None
    """Seconds left, 0 when qBittorrent cannot tell."""
    reason: Failure | None = None
    destination: str | None = None
    """Placed: where."""
    unplaced: str | None = None
    """To place: why the placement left it."""
    copied: bool = False
    """A file of it copied on the shelf rather than hardlinked."""


@dataclass(frozen=True, kw_only=True)
class DownloadView:
    download: Download
    progress: Progress


@dataclass(frozen=True, kw_only=True)
class Choice:
    """A release of a search to send, with its volumes as the page gives them."""

    release_id: str
    volumes: Volumes


@dataclass(frozen=True, kw_only=True)
class SendOrder:
    search_id: str
    work_id: str | None
    author: str
    series: str
    choices: tuple[Choice, ...]


@dataclass(frozen=True, kw_only=True)
class DownloadOptions:
    # Looks for a torrent in qBittorrent after it is added, and the seconds between two.
    tries: int = 3
    check_seconds: float = 8.0
    # Torrents fetched from Prowlarr and added to qBittorrent at the same time.
    parallel: int = 2
    # The downloads the page lists, the newest first.
    listed: int = 200
