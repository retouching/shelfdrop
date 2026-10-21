"""UploadRepository: the uploads and their chunks received."""

from collections.abc import Callable, Iterable, Sequence
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session

from shelfdrop.db.models import Upload as UploadRow
from shelfdrop.uploads.types import Upload, UploadState

INDEXES: Final = TypeAdapter(tuple[int, ...])
STATE: Final = TypeAdapter(UploadState)


def upload_of(row: UploadRow) -> Upload:
    return Upload(
        id=row.id,
        name=row.name,
        size=row.size,
        chunk_size=row.chunk_size,
        received=INDEXES.validate_json(row.received),
        sha256=row.sha256,
        state=STATE.validate_python(row.state),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class UploadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str, size: int, chunk_size: int, now: int) -> Upload:
        row = UploadRow(
            name=name,
            size=size,
            chunk_size=chunk_size,
            received="[]",
            sha256=None,
            state="receiving",
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        self.session.flush()
        return upload_of(row)

    def read(self, upload_id: int) -> Upload | None:
        row = self.session.get(UploadRow, upload_id)
        return None if row is None else upload_of(row)

    def find_receiving(self, name: str, size: int, chunk_size: int) -> Upload | None:
        """The latest upload of the same file still receiving its chunks: the page resumes it."""
        row = self.session.scalar(
            select(UploadRow)
            .where(
                UploadRow.name == name,
                UploadRow.size == size,
                UploadRow.chunk_size == chunk_size,
                UploadRow.state == "receiving",
            )
            .order_by(UploadRow.id.desc())
        )
        return None if row is None else upload_of(row)

    def mark_received(self, upload_id: int, received: Sequence[int], now: int) -> None:
        self.session.execute(
            update(UploadRow)
            .where(UploadRow.id == upload_id)
            .values(received=INDEXES.dump_json(tuple(sorted(received))).decode(), updated_at=now)
        )

    def mark(self, upload_id: int, state: UploadState, now: int, sha256: str | None = None) -> None:
        values: dict[str, object] = {"state": state, "updated_at": now}
        if sha256 is not None:
            values["sha256"] = sha256
        self.session.execute(update(UploadRow).where(UploadRow.id == upload_id).values(**values))

    def read_in(self, states: Iterable[UploadState]) -> list[Upload]:
        rows = self.session.scalars(
            select(UploadRow).where(UploadRow.state.in_(list(states))).order_by(UploadRow.id)
        )
        return [upload_of(row) for row in rows]

    def read_ids(self) -> set[int]:
        return set(self.session.scalars(select(UploadRow.id)))

    def delete(self, upload_ids: Sequence[int]) -> None:
        self.session.execute(delete(UploadRow).where(UploadRow.id.in_(list(upload_ids))))

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type UploadRepositoryFactory = Callable[[], UploadRepository]


def upload_repository_factory(engine: Engine) -> UploadRepositoryFactory:
    """Repositories on sessions of their own, for the placement worker."""

    def new() -> UploadRepository:
        return UploadRepository(Session(engine, expire_on_commit=False))

    return new
