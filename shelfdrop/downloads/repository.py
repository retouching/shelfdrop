"""DownloadRepository: the downloads, their torrents and their stages."""

from collections.abc import Callable, Sequence
from typing import Final, Literal

from pydantic import TypeAdapter
from sqlalchemy import Engine, and_, or_, select, update
from sqlalchemy.orm import Session

from shelfdrop.db.models import Download as DownloadRow
from shelfdrop.downloads.types import Download, DownloadMode, Failure, NewDownload, Stage
from shelfdrop.releases.types import Torrent, Volumes
from shelfdrop.works.types import Kind

VOLUME_KIND: Final = TypeAdapter[Literal["single", "range", "complete", "unknown"]](
    Literal["single", "range", "complete", "unknown"]
)
KIND: Final = TypeAdapter[Kind](Kind)
MODE: Final = TypeAdapter[DownloadMode](DownloadMode)
STAGE: Final = TypeAdapter[Stage](Stage)
FAILURE: Final = TypeAdapter[Failure | None](Failure | None)


def download_of(row: DownloadRow) -> Download:
    return Download(
        id=row.id,
        info_hash=row.info_hash,
        release_id=row.release_id,
        title=row.title,
        indexer=row.indexer,
        size=row.size,
        download_url=row.download_url,
        work_id=row.work_id,
        work_name=row.work_name,
        author=row.author,
        series=row.series,
        volumes=Volumes(
            kind=VOLUME_KIND.validate_python(row.volume_kind),
            first=row.volume_first,
            last=row.volume_last,
        ),
        kind=KIND.validate_python(row.kind),
        mode=MODE.validate_python(row.mode),
        category=row.category,
        stage=STAGE.validate_python(row.stage),
        failure=FAILURE.validate_python(row.failure),
        attempts=row.attempts,
        created_at=row.created_at,
        created_by=row.created_by,
        added_at=row.added_at,
        completed_at=row.completed_at,
        destination=row.destination,
        unplaced=row.unplaced,
        placing_percent=row.placing_percent,
    )


class DownloadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, new: NewDownload) -> Download:
        """A download to send (`sending`, a first attempt); its id once flushed."""
        row = DownloadRow(
            release_id=new.release_id,
            guid=new.guid,
            title=new.title,
            indexer_id=new.indexer_id,
            indexer=new.indexer,
            size=new.size,
            download_url=new.download_url,
            work_id=new.work_id,
            work_name=new.work_name,
            author=new.author,
            series=new.series,
            volume_kind=new.volumes.kind,
            volume_first=new.volumes.first,
            volume_last=new.volumes.last,
            kind=new.kind,
            mode=new.mode,
            category=new.category,
            stage="sending",
            attempts=1,
            created_at=new.created_at,
            created_by=new.created_by,
        )
        self.session.add(row)
        self.session.flush()
        return download_of(row)

    def read(self, download_id: int) -> Download | None:
        row = self.session.get(DownloadRow, download_id)
        return None if row is None else download_of(row)

    def read_recent(self, limit: int) -> list[Download]:
        """The newest downloads first."""
        rows = self.session.scalars(
            select(DownloadRow)
            .order_by(DownloadRow.created_at.desc(), DownloadRow.id.desc())
            .limit(limit)
        )
        return [download_of(row) for row in rows]

    def read_sending(self) -> list[int]:
        """The downloads a send left `sending` (the process stopped during it)."""
        return list(
            self.session.scalars(select(DownloadRow.id).where(DownloadRow.stage == "sending"))
        )

    def read_torrent(self, download_id: int) -> Torrent | None:
        """The torrent a send already read, sent again as it is."""
        row = self.session.get(DownloadRow, download_id)
        if row is None or (row.torrent is None and row.magnet is None):
            return None
        return Torrent(file=row.torrent, magnet=row.magnet)

    def save_torrent(self, download_id: int, torrent: Torrent, info_hash: str) -> None:
        self.session.execute(
            update(DownloadRow)
            .where(DownloadRow.id == download_id)
            .values(torrent=torrent.file, magnet=torrent.magnet, info_hash=info_hash)
        )

    def mark_added(self, download_id: int, now: int) -> None:
        """qBittorrent took it: the first time is kept."""
        self.session.execute(
            update(DownloadRow)
            .where(DownloadRow.id == download_id, DownloadRow.added_at.is_(None))
            .values(added_at=now)
        )

    def mark_sent(self, download_id: int, now: int) -> None:
        self.session.execute(
            update(DownloadRow)
            .where(DownloadRow.id == download_id)
            .values(stage="sent", failure=None, sent_at=now)
        )

    def mark_failed(self, download_id: int, failure: Failure) -> None:
        self.session.execute(
            update(DownloadRow)
            .where(DownloadRow.id == download_id)
            .values(stage="failed", failure=failure)
        )

    def mark_completed(self, download_ids: Sequence[int], now: int) -> list[int]:
        """qBittorrent has them all: those still `sent` are completed; their ids (the page and
        the placement worker may both see the end: one of them only completes each)."""
        return list(
            self.session.scalars(
                update(DownloadRow)
                .where(DownloadRow.id.in_(download_ids), DownloadRow.stage == "sent")
                .values(stage="completed", completed_at=now)
                .returning(DownloadRow.id)
            )
        )

    def read_sent(self) -> list[Download]:
        """The downloads qBittorrent has, not complete yet."""
        rows = self.session.scalars(
            select(DownloadRow).where(
                DownloadRow.stage == "sent", DownloadRow.info_hash.is_not(None)
            )
        )
        return [download_of(row) for row in rows]

    def read_to_place(self) -> list[Download]:
        """The automatic downloads complete, waiting for their placement, the oldest first."""
        rows = self.session.scalars(
            select(DownloadRow)
            .where(DownloadRow.stage == "completed", DownloadRow.mode == "auto")
            .order_by(DownloadRow.completed_at, DownloadRow.id)
        )
        return [download_of(row) for row in rows]

    def read_left(self) -> list[Download]:
        """The downloads Ranger takes: those the placement left, and the manual ones
        complete."""
        rows = self.session.scalars(
            select(DownloadRow)
            .where(
                or_(
                    DownloadRow.stage == "unplaced",
                    and_(DownloadRow.stage == "completed", DownloadRow.mode == "manual"),
                )
            )
            .order_by(DownloadRow.id)
        )
        return [download_of(row) for row in rows]

    def mark_placed(self, download_id: int, destination: str, now: int) -> None:
        self.session.execute(
            update(DownloadRow)
            .where(DownloadRow.id == download_id)
            .values(stage="placed", destination=destination, placing_percent=None, placed_at=now)
        )

    def mark_unplaced(self, download_id: int, reason: str, now: int) -> None:
        """Left to Ranger: placed by hand."""
        self.session.execute(
            update(DownloadRow)
            .where(DownloadRow.id == download_id)
            .values(stage="unplaced", unplaced=reason, placing_percent=None, placed_at=now)
        )

    def mark_placing(self, download_id: int, percent: int) -> None:
        self.session.execute(
            update(DownloadRow).where(DownloadRow.id == download_id).values(placing_percent=percent)
        )

    def mark_retried(self, download_id: int) -> None:
        """Sent again: one more attempt."""
        self.session.execute(
            update(DownloadRow)
            .where(DownloadRow.id == download_id)
            .values(stage="sending", failure=None, attempts=DownloadRow.attempts + 1)
        )

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type DownloadRepositoryFactory = Callable[[], DownloadRepository]


def download_repository_factory(engine: Engine) -> DownloadRepositoryFactory:
    """New repositories on their own session, for the sends that outlive their request; the
    caller closes each."""

    def new() -> DownloadRepository:
        return DownloadRepository(Session(engine, expire_on_commit=False))

    return new
