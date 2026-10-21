"""Download: a release sent to qBittorrent, what it is for, where it is, and who sent it."""

from sqlalchemy import Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The id qBittorrent names the torrent by (shelfdrop.utils.torrent), once the torrent is
    # read; the torrent itself, a file or a magnet link, sent again as it is by a retry.
    info_hash: Mapped[str | None] = mapped_column(String(40), index=True)
    torrent: Mapped[bytes | None] = mapped_column(LargeBinary)
    magnet: Mapped[str | None] = mapped_column(Text)
    # The release, as Prowlarr gave it: its download link is kept without the key of Prowlarr.
    release_id: Mapped[str] = mapped_column(String(16))
    guid: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    indexer_id: Mapped[int] = mapped_column(Integer)
    indexer: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer)
    download_url: Mapped[str | None] = mapped_column(Text)
    # What it is for: the work (its id in the work search, its name or the text of a manual
    # search), the author and the series of the shelf, the volumes, the kind.
    work_id: Mapped[str | None] = mapped_column(String(200))
    work_name: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(200))
    series: Mapped[str] = mapped_column(String(200))
    volume_kind: Mapped[str] = mapped_column(String(10))
    volume_first: Mapped[int | None] = mapped_column(Integer)
    volume_last: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    # `auto` (shelved alone) or `manual` (to place by hand), and its category of qBittorrent.
    mode: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(64))
    # `sending`, `sent` (found in qBittorrent by its hash), `completed`, `placed` (on the
    # shelf), `unplaced` (to place in Ranger) or `failed`, with its reason (`not_received`,
    # `duplicate`).
    stage: Mapped[str] = mapped_column(String(10), index=True)
    failure: Mapped[str | None] = mapped_column(String(20))
    # Sends to qBittorrent, the first one and each retry.
    attempts: Mapped[int] = mapped_column(Integer)
    # Unix seconds: asked (by the account `created_by`), first added to qBittorrent, found
    # there, completed.
    created_at: Mapped[int] = mapped_column(Integer, index=True)
    created_by: Mapped[str] = mapped_column(String(255))
    added_at: Mapped[int | None] = mapped_column(Integer)
    sent_at: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[int | None] = mapped_column(Integer)
    # The placement of a download complete: where it went (the library, then the series), or why it
    # was not placed alone (`chapters`, `no_volume`...: placed by hand in Ranger), the percent of
    # its merge of MP3 tracks while it runs, and when it ended.
    destination: Mapped[str | None] = mapped_column(String(300))
    unplaced: Mapped[str | None] = mapped_column(String(20))
    placing_percent: Mapped[int | None] = mapped_column(Integer)
    placed_at: Mapped[int | None] = mapped_column(Integer)
