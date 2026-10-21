"""PlacementRepository: the files put on the shelf, and the writes the API asks for in the
libraries."""

from collections.abc import Callable, Sequence
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from shelfdrop.db.models import LibraryTask as LibraryTaskRow
from shelfdrop.db.models import ShelfFile as ShelfFileRow
from shelfdrop.placement.types import LibraryTask, PlacedFile, ShelfFile, TaskKind
from shelfdrop.works.types import Kind

KIND: Final = TypeAdapter[Kind](Kind)
TASK: Final = TypeAdapter[TaskKind](TaskKind)


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

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type PlacementRepositoryFactory = Callable[[], PlacementRepository]


def placement_repository_factory(engine: Engine) -> PlacementRepositoryFactory:
    def new() -> PlacementRepository:
        return PlacementRepository(Session(engine, expire_on_commit=False))

    return new
