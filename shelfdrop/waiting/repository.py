"""WaitingRepository: the searches kept waiting."""

import json
from collections.abc import Callable, Sequence
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from shelfdrop.db.models import WaitingSearch as WaitingRow
from shelfdrop.waiting.types import Target, Waiting, WaitingState, Wanted
from shelfdrop.works.types import Kind

KIND: Final = TypeAdapter[Kind](Kind)
TARGET: Final = TypeAdapter[Target](Target)
STATE: Final = TypeAdapter[WaitingState](WaitingState)


def waiting_of(row: WaitingRow) -> Waiting:
    return Waiting(
        id=row.id,
        work_id=row.work_id,
        title=row.title,
        author=row.author,
        kind=KIND.validate_python(row.kind),
        names=tuple(json.loads(row.names)),
        wanted=Wanted(
            target=TARGET.validate_python(row.target),
            volume=row.volume,
            chapter_from=row.chapter_from,
            chapter_to=row.chapter_to,
        ),
        state=STATE.validate_python(row.state),
        releases=row.releases,
        attempts=row.attempts,
        created_at=row.created_at,
        created_by=row.created_by,
        searched_at=row.searched_at,
    )


class WaitingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read_active(self) -> list[Waiting]:
        """Those not done, the newest first."""
        rows = self.session.scalars(
            select(WaitingRow).where(WaitingRow.done_at.is_(None)).order_by(WaitingRow.id.desc())
        )
        return [waiting_of(r) for r in rows]

    def read(self, waiting_id: int) -> Waiting | None:
        row = self.session.get(WaitingRow, waiting_id)
        return None if row is None or row.done_at is not None else waiting_of(row)

    def add(
        self,
        *,
        work_id: str | None,
        title: str,
        author: str,
        kind: Kind,
        names: Sequence[str],
        wanted: Wanted,
        now: int,
        created_by: str,
    ) -> Waiting:
        row = WaitingRow(
            work_id=work_id,
            title=title,
            author=author,
            kind=kind,
            names=json.dumps(list(names), ensure_ascii=False),
            target=wanted.target,
            volume=wanted.volume,
            chapter_from=wanted.chapter_from,
            chapter_to=wanted.chapter_to,
            state="waiting",
            releases=0,
            attempts=0,
            created_at=now,
            created_by=created_by,
        )
        self.session.add(row)
        self.session.flush()
        return waiting_of(row)

    def mark_searched(self, waiting_id: int, state: WaitingState, releases: int, now: int) -> None:
        self.session.execute(
            update(WaitingRow)
            .where(WaitingRow.id == waiting_id)
            .values(
                state=state,
                releases=releases,
                searched_at=now,
                attempts=WaitingRow.attempts + 1,
            )
        )

    def advance(self, waiting_id: int, chapter_from: float) -> None:
        self.session.execute(
            update(WaitingRow).where(WaitingRow.id == waiting_id).values(chapter_from=chapter_from)
        )

    def mark_done(self, waiting_id: int, now: int) -> None:
        self.session.execute(
            update(WaitingRow).where(WaitingRow.id == waiting_id).values(done_at=now)
        )

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type WaitingRepositoryFactory = Callable[[], WaitingRepository]


def waiting_repository_factory(engine: Engine) -> WaitingRepositoryFactory:
    def new() -> WaitingRepository:
        return WaitingRepository(Session(engine, expire_on_commit=False))

    return new
