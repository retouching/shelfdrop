"""Fakes of the uploads: the table in memory."""

import dataclasses
import itertools
from collections.abc import Iterable, Sequence
from typing import override

from shelfdrop.uploads.repository import UploadRepository
from shelfdrop.uploads.types import Upload, UploadState
from tests.unit.support import no_session


class FakeUploadRepository(UploadRepository):
    """The uploads in memory; it counts the commits."""

    def __init__(self) -> None:
        super().__init__(no_session())
        self.rows: dict[int, Upload] = {}
        self.ids = itertools.count(1)
        self.commits = 0

    @override
    def add(self, name: str, size: int, chunk_size: int, now: int) -> Upload:
        upload = Upload(
            id=next(self.ids),
            name=name,
            size=size,
            chunk_size=chunk_size,
            received=(),
            sha256=None,
            state="receiving",
            created_at=now,
            updated_at=now,
        )
        self.rows[upload.id] = upload
        return upload

    @override
    def read(self, upload_id: int) -> Upload | None:
        return self.rows.get(upload_id)

    @override
    def find_receiving(self, name: str, size: int, chunk_size: int) -> Upload | None:
        found = [
            u
            for u in self.rows.values()
            if (u.name, u.size, u.chunk_size, u.state) == (name, size, chunk_size, "receiving")
        ]
        return found[-1] if found else None

    @override
    def mark_received(self, upload_id: int, received: Sequence[int], now: int) -> None:
        self.rows[upload_id] = dataclasses.replace(
            self.rows[upload_id], received=tuple(sorted(received)), updated_at=now
        )

    @override
    def mark(self, upload_id: int, state: UploadState, now: int, sha256: str | None = None) -> None:
        row = self.rows[upload_id]
        self.rows[upload_id] = dataclasses.replace(
            row, state=state, updated_at=now, sha256=sha256 or row.sha256
        )

    @override
    def read_in(self, states: Iterable[UploadState]) -> list[Upload]:
        wanted = set(states)
        return [u for _, u in sorted(self.rows.items()) if u.state in wanted]

    @override
    def read_ids(self) -> set[int]:
        return set(self.rows)

    @override
    def delete(self, upload_ids: Sequence[int]) -> None:
        for upload_id in upload_ids:
            self.rows.pop(upload_id, None)

    @override
    def commit(self) -> None:
        self.commits += 1

    @override
    def close(self) -> None:
        pass
