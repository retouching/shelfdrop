"""What the page shows of a download, from its stage and the torrent qBittorrent lists. Pure:
no I/O."""

from typing import Final

from shelfdrop.clients.types import TorrentInfo
from shelfdrop.downloads.types import (
    CATEGORIES,
    MANUAL_CATEGORY,
    Download,
    DownloadMode,
    Progress,
)
from shelfdrop.journal.types import NewEvent
from shelfdrop.works.types import Kind

# The states of qBittorrent of a torrent it has all of (the WebUI API: `stoppedUP` from
# qBittorrent 5, `pausedUP` before).
COMPLETE: Final = frozenset(
    {"uploading", "pausedUP", "stoppedUP", "queuedUP", "stalledUP", "checkingUP", "forcedUP"}
)
# The states of a torrent that downloads, or tries to (no peer: `stalledDL`). The others
# (`metaDL`, `queuedDL`, `pausedDL`, `checkingDL`, `allocating`, `moving`, `error`...) wait.
DOWNLOADING: Final = frozenset({"downloading", "forcedDL", "stalledDL"})
# The `eta` of qBittorrent when it cannot tell.
UNKNOWN_ETA: Final = 8640000


def category_of(kind: Kind, mode: DownloadMode) -> str:
    return MANUAL_CATEGORY if mode == "manual" else CATEGORIES[kind]


def is_complete(info: TorrentInfo) -> bool:
    return info.progress >= 1 or info.state in COMPLETE


def finished(download: Download) -> Progress:
    """A download qBittorrent has all of: an automatic one waits for its placement, a manual
    one is placed by hand."""
    return Progress(state="placing" if download.mode == "auto" else "to_place")


def progress_of(download: Download, info: TorrentInfo | None) -> Progress:
    """`info`: the torrent of `download` qBittorrent lists, None when it lists none (or does not
    answer)."""
    match download.stage:
        case "failed":
            return Progress(state="failed", reason=download.failure or "not_received")
        case "completed":
            return finished(download)
        case "sending":
            return Progress(state="waiting")
        case "sent":
            if info is None:
                return Progress(state="waiting")
            if is_complete(info):
                return finished(download)
            if info.state in DOWNLOADING:
                return Progress(
                    state="downloading",
                    percent=int(info.progress * 100),
                    speed=max(0, info.speed),
                    eta=info.eta if 0 <= info.eta < UNKNOWN_ETA else 0,
                )
            return Progress(state="waiting")


def completion_event(download: Download, now: int) -> NewEvent:
    """The end of a download: `downloaded` for an automatic one, before its placement;
    `to_place` for a manual one, placed by hand in Ranger."""
    if download.mode == "manual":
        return NewEvent(
            type="to_place",
            group=f"to_place:manual:{download.created_by}:{download.created_at}",
            facts={"work": download.work_name, "release": download.title, "reason": "manual"},
        )
    seconds = now - download.added_at if download.added_at is not None else 0
    return NewEvent(
        type="downloaded",
        group=f"downloaded:{download.created_by}:{download.created_at}:{download.work_name}",
        facts={
            "work": download.series or download.work_name,
            "release": download.title,
            "size": download.size,
            "seconds": max(0, seconds),
        },
    )
