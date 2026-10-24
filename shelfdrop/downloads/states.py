"""What the page shows of a download, from its stage and the torrent the torrent client lists
(its generic status, `shelfdrop.clients.torrents.types.TorrentStatus`). Pure: no I/O."""

from shelfdrop.clients.torrents.types import TorrentInfo
from shelfdrop.downloads.types import (
    CATEGORIES,
    MANUAL_CATEGORY,
    Download,
    DownloadMode,
    Progress,
)
from shelfdrop.journal.types import NewEvent
from shelfdrop.works.types import Kind


def category_of(kind: Kind, mode: DownloadMode) -> str:
    return MANUAL_CATEGORY if mode == "manual" else CATEGORIES[kind]


def is_complete(info: TorrentInfo) -> bool:
    return info.status == "complete"


def finished(download: Download) -> Progress:
    """A download the torrent client has all of: an automatic one waits for its placement (the
    percent of its merge of MP3 tracks while it runs), a manual one is placed by hand."""
    if download.mode == "manual":
        return Progress(state="to_place", unplaced="manual")
    return Progress(state="placing", percent=download.placing_percent)


def progress_of(download: Download, info: TorrentInfo | None) -> Progress:
    """`info`: the torrent of `download` the torrent client lists, None when it lists none (or
    does not answer)."""
    match download.stage:
        case "failed":
            return Progress(state="failed", reason=download.failure or "not_received")
        case "placed":
            return Progress(
                state="placed", destination=download.destination, copied=download.copied
            )
        case "unplaced":
            return Progress(state="to_place", unplaced=download.unplaced, copied=download.copied)
        case "completed":
            return finished(download)
        case "sending":
            return Progress(state="waiting")
        case "sent":
            if info is None:
                return Progress(state="waiting")
            if is_complete(info):
                return finished(download)
            # A torrent stalled (no peer) still downloads, as far as the page tells; one waiting
            # or stopped on an error waits.
            if info.status in ("downloading", "stalled"):
                return Progress(
                    state="downloading",
                    percent=int(info.progress * 100),
                    speed=max(0, info.speed),
                    eta=max(0, info.eta) if info.eta is not None else 0,
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
