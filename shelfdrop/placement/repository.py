"""PlacementRepository: the files put on the shelf, and the writes the API asks for in the
libraries."""

from collections.abc import Callable, Sequence
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import Engine, delete, func, or_, select, update
from sqlalchemy.orm import Session

from shelfdrop.db.models import LibraryTask as LibraryTaskRow
from shelfdrop.db.models import PlaceItem as PlaceItemRow
from shelfdrop.db.models import ShelfFile as ShelfFileRow
from shelfdrop.placement.types import (
    ItemOrigin,
    ItemState,
    LibraryTask,
    NewItem,
    PlacedFile,
    PlaceItem,
    PlaceRequest,
    ShelfFile,
    TaskKind,
)
from shelfdrop.works.types import Kind

KIND: Final = TypeAdapter[Kind](Kind)
TASK: Final = TypeAdapter[TaskKind](TaskKind)
ORIGIN: Final = TypeAdapter[ItemOrigin](ItemOrigin)
STATE: Final = TypeAdapter[ItemState](ItemState)
REQUEST: Final = TypeAdapter[PlaceRequest](PlaceRequest)
PATHS: Final = TypeAdapter[tuple[str, ...]](tuple[str, ...])
CHAPTERS: Final = TypeAdapter[tuple[float, ...]](tuple[float, ...])
VOLUMES: Final = TypeAdapter[tuple[int, ...]](tuple[int, ...])
# The states of a file of Ranger still to place.
OPEN: Final = ("unlinked", "chapters", "misplaced")


def file_of(row: ShelfFileRow) -> ShelfFile:
    return ShelfFile(
        id=row.id,
        kind=KIND.validate_python(row.kind),
        work_id=row.work_id,
        series=row.series,
        author=row.author,
        volume=row.volume,
        chapter=row.chapter,
        path=row.path,
        locked=row.locked,
        created_at=row.created_at,
    )


def item_of(row: PlaceItemRow) -> PlaceItem:
    return PlaceItem(
        id=row.id,
        origin=ORIGIN.validate_python(row.origin),
        download_id=row.download_id,
        kind=None if row.kind is None else KIND.validate_python(row.kind),
        name=row.name,
        path=row.path,
        files=PATHS.validate_json(row.files),
        size=row.size,
        state=STATE.validate_python(row.state),
        reason=row.reason,
        chapters=CHAPTERS.validate_json(row.chapters),
        series=row.series,
        existing=VOLUMES.validate_json(row.existing),
        loose=CHAPTERS.validate_json(row.loose),
        work_id=row.work_id,
        author=row.author,
        request=None if row.request is None else REQUEST.validate_json(row.request),
        error=row.error,
        destination=row.destination,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PlacementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_files(self, files: Sequence[PlacedFile], now: int) -> None:
        for placed in files:
            self.session.add(
                ShelfFileRow(
                    download_id=placed.download_id,
                    kind=placed.kind,
                    work_id=placed.work_id,
                    series=placed.series,
                    author=placed.author,
                    volume=placed.volume,
                    chapter=placed.chapter,
                    path=placed.path,
                    locked=False,
                    created_at=now,
                )
            )

    def read_unlocked(self, since: int) -> list[ShelfFile]:
        """The files placed since `since` whose metadata Jellyfin does not hold yet."""
        rows = self.session.scalars(
            select(ShelfFileRow)
            .where(ShelfFileRow.locked.is_(False), ShelfFileRow.created_at >= since)
            .order_by(ShelfFileRow.id)
        )
        return [file_of(row) for row in rows]

    def read_files(self) -> list[ShelfFile]:
        """Every file placed, in the order of their placement."""
        return [
            file_of(row)
            for row in self.session.scalars(select(ShelfFileRow).order_by(ShelfFileRow.id))
        ]

    def mark_locked(self, file_ids: Sequence[int]) -> None:
        self.session.execute(
            update(ShelfFileRow).where(ShelfFileRow.id.in_(file_ids)).values(locked=True)
        )

    def read_shelved(self, work_id: str | None, series: str, kind: Kind) -> list[ShelfFile]:
        """The files placed of a work (by its id, or by its series without one)."""
        found = select(ShelfFileRow).where(ShelfFileRow.kind == kind)
        found = found.where(
            ShelfFileRow.work_id == work_id
            if work_id is not None
            else ShelfFileRow.series == series
        )
        return [file_of(row) for row in self.session.scalars(found)]

    def add_task(self, kind: TaskKind, path: str, data: bytes, now: int) -> None:
        self.session.add(
            LibraryTaskRow(kind=kind, path=path, data=data, state="pending", created_at=now)
        )

    def read_tasks(self) -> list[LibraryTask]:
        rows = self.session.scalars(
            select(LibraryTaskRow)
            .where(LibraryTaskRow.state == "pending")
            .order_by(LibraryTaskRow.id)
        )
        return [
            LibraryTask(id=r.id, kind=TASK.validate_python(r.kind), path=r.path, data=r.data)
            for r in rows
        ]

    def mark_task(self, task_id: int, state: str, now: int) -> None:
        self.session.execute(
            update(LibraryTaskRow)
            .where(LibraryTaskRow.id == task_id)
            .values(state=state, done_at=now)
        )

    def remove_files(self, paths: Sequence[str]) -> None:
        """The files no longer on the shelf (chapters merged into their volume, a file moved)."""
        if paths:
            self.session.execute(delete(ShelfFileRow).where(ShelfFileRow.path.in_(paths)))

    def read_download_files(self, download_id: int) -> list[ShelfFile]:
        """The files a download put on the shelf (by the worker alone, or from Ranger)."""
        rows = self.session.scalars(
            select(ShelfFileRow)
            .where(ShelfFileRow.download_id == download_id)
            .order_by(ShelfFileRow.id)
        )
        return [file_of(row) for row in rows]

    def read_shelf_paths(self) -> set[str]:
        """The paths of every file the placement put on the shelf."""
        return set(self.session.scalars(select(ShelfFileRow.path)))

    def find_shelved(self, text: str, limit: int) -> list[ShelfFile]:
        """The files of the shelf whose path holds `text` (case aside), the latest first."""
        pattern = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        rows = self.session.scalars(
            select(ShelfFileRow)
            .where(ShelfFileRow.path.ilike(pattern, escape="\\"))
            .order_by(ShelfFileRow.id.desc())
            .limit(limit)
        )
        return [file_of(row) for row in rows]

    def read_shelf_file(self, file_id: int) -> ShelfFile | None:
        row = self.session.get(ShelfFileRow, file_id)
        return None if row is None else file_of(row)

    def add_item(self, item: NewItem, now: int) -> int:
        row = PlaceItemRow(
            origin=item.origin,
            download_id=item.download_id,
            kind=item.kind,
            name=item.name[:300],
            path=item.path,
            files=PATHS.dump_json(item.files).decode(),
            size=item.size,
            state=item.state,
            reason=item.reason,
            chapters=CHAPTERS.dump_json(item.chapters).decode(),
            series=item.series[:200],
            existing=VOLUMES.dump_json(item.existing).decode(),
            loose=CHAPTERS.dump_json(item.loose).decode(),
            work_id=item.work_id,
            author=item.author[:200],
            request=None,
            error=None,
            destination=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.flush()
        return row.id

    def update_item(self, item_id: int, item: NewItem, now: int) -> None:
        """What the worker found again in an open file of Ranger (a scan, the rest of a release
        in chapters kept)."""
        self.session.execute(
            update(PlaceItemRow)
            .where(PlaceItemRow.id == item_id)
            .values(
                kind=item.kind,
                name=item.name[:300],
                files=PATHS.dump_json(item.files).decode(),
                size=item.size,
                state=item.state,
                reason=item.reason,
                chapters=CHAPTERS.dump_json(item.chapters).decode(),
                series=item.series[:200],
                existing=VOLUMES.dump_json(item.existing).decode(),
                loose=CHAPTERS.dump_json(item.loose).decode(),
                updated_at=now,
            )
        )

    def set_item_shelf(
        self, item_id: int, existing: tuple[int, ...], loose: tuple[float, ...]
    ) -> None:
        """The volumes and the loose chapters of the series of a file of Ranger, read again."""
        self.session.execute(
            update(PlaceItemRow)
            .where(PlaceItemRow.id == item_id)
            .values(
                existing=VOLUMES.dump_json(existing).decode(),
                loose=CHAPTERS.dump_json(loose).decode(),
            )
        )

    def read_items(self, *, placed: bool) -> list[PlaceItem]:
        """The files of Ranger still to place (and those placed with `placed`), the latest
        first."""
        found = select(PlaceItemRow).order_by(PlaceItemRow.id.desc())
        if not placed:
            found = found.where(PlaceItemRow.state.in_(OPEN))
        return [item_of(row) for row in self.session.scalars(found)]

    def read_item(self, item_id: int) -> PlaceItem | None:
        row = self.session.get(PlaceItemRow, item_id)
        return None if row is None else item_of(row)

    def count_open(self) -> int:
        return (
            self.session.scalar(
                select(func.count()).select_from(PlaceItemRow).where(PlaceItemRow.state.in_(OPEN))
            )
            or 0
        )

    def read_item_downloads(self) -> set[int]:
        """The downloads that have their files in Ranger already."""
        return {
            n
            for n in self.session.scalars(
                select(PlaceItemRow.download_id).where(PlaceItemRow.download_id.is_not(None))
            )
            if n is not None
        }

    def read_open_of(self, origin: ItemOrigin, *, ignored: bool = False) -> list[PlaceItem]:
        """The files of `origin` still to place (and those ignored with `ignored`)."""
        states = (*OPEN, "ignored") if ignored else OPEN
        rows = self.session.scalars(
            select(PlaceItemRow).where(
                PlaceItemRow.origin == origin, PlaceItemRow.state.in_(states)
            )
        )
        return [item_of(row) for row in rows]

    def count_open_of_download(self, download_id: int) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(PlaceItemRow)
                .where(PlaceItemRow.download_id == download_id, PlaceItemRow.state.in_(OPEN))
            )
            or 0
        )

    def delete_items(self, item_ids: Sequence[int]) -> None:
        if item_ids:
            self.session.execute(delete(PlaceItemRow).where(PlaceItemRow.id.in_(item_ids)))

    def ask(self, item_id: int, request: PlaceRequest, now: int) -> bool:
        """The request of the page on an open file with none pending; False otherwise."""
        done = self.session.execute(
            update(PlaceItemRow)
            .where(
                PlaceItemRow.id == item_id,
                PlaceItemRow.state.in_(OPEN),
                PlaceItemRow.request.is_(None),
            )
            .values(request=REQUEST.dump_json(request).decode(), error=None, updated_at=now)
        )
        return bool(getattr(done, "rowcount", 0))

    def read_asked(self) -> list[PlaceItem]:
        rows = self.session.scalars(
            select(PlaceItemRow)
            .where(PlaceItemRow.request.is_not(None), PlaceItemRow.state.in_(OPEN))
            .order_by(PlaceItemRow.id)
        )
        return [item_of(row) for row in rows]

    def mark_item_placed(self, item_id: int, destination: str, now: int) -> None:
        self.session.execute(
            update(PlaceItemRow)
            .where(PlaceItemRow.id == item_id)
            .values(
                state="placed", request=None, error=None, destination=destination, updated_at=now
            )
        )

    def mark_item_ignored(self, item_id: int, now: int) -> None:
        """The file left where it is, out of the files to place."""
        self.session.execute(
            update(PlaceItemRow)
            .where(PlaceItemRow.id == item_id)
            .values(state="ignored", request=None, error=None, updated_at=now)
        )

    def resume(self, item_id: int, state: ItemState, now: int) -> bool:
        """An ignored file back to `state`; False when it is not ignored."""
        done = self.session.execute(
            update(PlaceItemRow)
            .where(PlaceItemRow.id == item_id, PlaceItemRow.state == "ignored")
            .values(state=state, request=None, error=None, updated_at=now)
        )
        return bool(getattr(done, "rowcount", 0))

    def read_items_of_download(self, download_id: int) -> list[PlaceItem]:
        rows = self.session.scalars(
            select(PlaceItemRow)
            .where(PlaceItemRow.download_id == download_id)
            .order_by(PlaceItemRow.id)
        )
        return [item_of(row) for row in rows]

    def mark_item_failed(self, item_id: int, error: str, now: int) -> None:
        """The request not done: the file stays in Ranger with the reason."""
        self.session.execute(
            update(PlaceItemRow)
            .where(PlaceItemRow.id == item_id)
            .values(request=None, error=error, updated_at=now)
        )

    def mark_item_kept(
        self, item_id: int, files: Sequence[str], chapters: Sequence[float], now: int
    ) -> None:
        """Part of a release in chapters placed: the rest stays in Ranger."""
        self.session.execute(
            update(PlaceItemRow)
            .where(PlaceItemRow.id == item_id)
            .values(
                request=None,
                error=None,
                files=PATHS.dump_json(tuple(files)).decode(),
                chapters=CHAPTERS.dump_json(tuple(chapters)).decode(),
                updated_at=now,
            )
        )

    def record_scan(self, now: int) -> None:
        """A scan of the libraries ended (the daily one, or the one the page asked)."""
        self.session.add(
            LibraryTaskRow(
                kind="scan", path="", data=b"", state="done", created_at=now, done_at=now
            )
        )

    def last_scan(self) -> int | None:
        """When the last scan of the libraries ended (Unix seconds)."""
        return self.session.scalar(
            select(func.max(LibraryTaskRow.done_at)).where(
                LibraryTaskRow.kind == "scan", LibraryTaskRow.state == "done"
            )
        )

    def has_pending_scan(self) -> bool:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(LibraryTaskRow)
                .where(
                    LibraryTaskRow.kind == "scan",
                    or_(LibraryTaskRow.state == "pending", LibraryTaskRow.state == "running"),
                )
            )
            or 0
        ) > 0

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type PlacementRepositoryFactory = Callable[[], PlacementRepository]


def placement_repository_factory(engine: Engine) -> PlacementRepositoryFactory:
    def new() -> PlacementRepository:
        return PlacementRepository(Session(engine, expire_on_commit=False))

    return new
