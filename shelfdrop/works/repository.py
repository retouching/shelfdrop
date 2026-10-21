"""WorkRepository: the cache of the answers of the metadata sources and of the merged works."""

from collections.abc import Iterable, Mapping
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from shelfdrop.db.models import CachedWork, SourceAnswer
from shelfdrop.works.types import Candidate, SourceName, Work

CANDIDATES: Final = TypeAdapter(tuple[Candidate, ...])
WORK: Final = TypeAdapter(Work)


class WorkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read_answers(
        self, sources: Iterable[SourceName], query: str, now: int
    ) -> dict[SourceName, tuple[Candidate, ...]]:
        """The answers of `sources` to `query` that have not expired, by source."""
        rows = self.session.scalars(
            select(SourceAnswer).where(
                SourceAnswer.source.in_(list(sources)),
                SourceAnswer.query == query,
                SourceAnswer.expires_at > now,
            )
        )
        found: dict[SourceName, tuple[Candidate, ...]] = {}
        for row in rows:
            source: SourceName = row.source  # type: ignore[assignment]  # written from a SourceName
            found[source] = CANDIDATES.validate_json(row.candidates)
        return found

    def save_answers(
        self, answers: Mapping[SourceName, tuple[Candidate, ...]], query: str, expires_at: int
    ) -> None:
        for source, candidates in answers.items():
            self.session.merge(
                SourceAnswer(
                    source=source,
                    query=query,
                    candidates=CANDIDATES.dump_json(candidates).decode(),
                    expires_at=expires_at,
                )
            )

    def save_works(self, works: Iterable[Work], expires_at: int) -> None:
        for work in works:
            self.session.merge(
                CachedWork(id=work.id, work=WORK.dump_json(work).decode(), expires_at=expires_at)
            )

    def read_work(self, work_id: str, now: int) -> Work | None:
        row = self.session.scalar(
            select(CachedWork).where(CachedWork.id == work_id, CachedWork.expires_at > now)
        )
        return None if row is None else WORK.validate_json(row.work)

    def remove_expired(self, now: int) -> None:
        self.session.execute(delete(SourceAnswer).where(SourceAnswer.expires_at <= now))
        self.session.execute(delete(CachedWork).where(CachedWork.expires_at <= now))

    def commit(self) -> None:
        self.session.commit()
