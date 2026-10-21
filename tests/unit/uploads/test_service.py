import hashlib
from pathlib import Path

import pytest

from shelfdrop.uploads.exceptions import (
    ChunkRefusedError,
    UploadCorruptError,
    UploadDoneError,
    UploadNotFoundError,
    UploadRefusedError,
)
from shelfdrop.uploads.service import UploadService
from shelfdrop.uploads.store import UploadStore
from shelfdrop.uploads.types import UploadOptions
from tests.unit.support import FakeJournal
from tests.unit.uploads.support import FakeUploadRepository
from tests.unit.works.support import FixedClock

DATA = b"0123456789" * 2 + b"abc"


def new_service(tmp_path: Path) -> tuple[UploadService, FakeUploadRepository, FakeJournal]:
    repository = FakeUploadRepository()
    journal = FakeJournal()
    service = UploadService(
        repository,
        UploadStore(tmp_path),
        journal,
        UploadOptions(chunk_bytes=10, max_bytes=100),
        FixedClock(),
    )
    return service, repository, journal


def test_a_file_sent_in_chunks_is_put_together_checked_and_told(tmp_path: Path) -> None:
    service, repository, journal = new_service(tmp_path)
    upload, new = service.start("C:\\livres\\Berserk  T01.cbz", len(DATA))
    assert (new, upload.name, upload.chunk_size) == (True, "Berserk T01.cbz", 10)

    service.receive(upload.id, 2, DATA[20:])
    service.receive(upload.id, 0, DATA[:10])
    again, new = service.start("Berserk T01.cbz", len(DATA))
    assert (again.id, again.received, new) == (upload.id, (0, 2), False)
    service.receive(upload.id, 1, DATA[10:20])
    done = service.finish(upload.id, hashlib.sha256(DATA).hexdigest().upper())

    assert done.state == "verified"
    assert done.sha256 == hashlib.sha256(DATA).hexdigest()
    assert (tmp_path / str(upload.id) / "Berserk T01.cbz").read_bytes() == DATA
    [told] = journal.of("uploaded")
    assert told.facts == {"file": "Berserk T01.cbz", "size": len(DATA), "type": "CBZ"}
    with pytest.raises(UploadDoneError):
        service.receive(upload.id, 0, DATA[:10])
    assert repository.commits > 0


def test_a_corrupt_file_is_removed_and_told(tmp_path: Path) -> None:
    service, repository, journal = new_service(tmp_path)
    upload, _ = service.start("Berserk.epub", 5)
    service.receive(upload.id, 0, b"hello")

    with pytest.raises(UploadCorruptError):
        service.finish(upload.id, "0" * 64)

    assert repository.rows[upload.id].state == "corrupt"
    assert not (tmp_path / str(upload.id)).exists()
    [failed] = journal.of("failed")
    assert failed.facts["what"] == "upload_corrupt"
    with pytest.raises(UploadDoneError):
        service.finish(upload.id, "0" * 64)


@pytest.mark.parametrize(
    ("name", "size", "reason"),
    [
        ("Berserk.exe", 5, "type"),
        ("Berserk.cbz", 101, "size"),
        ("Berserk.cbz", 0, "size"),
        (".cbz", 5, "name"),
        ("x" * 201 + ".cbz", 5, "name"),
    ],
)
def test_a_file_the_page_cannot_send_is_refused(
    tmp_path: Path, name: str, size: int, reason: str
) -> None:
    service, _, _ = new_service(tmp_path)
    with pytest.raises(UploadRefusedError) as refused:
        service.start(name, size)
    assert refused.value.reason == reason


def test_a_chunk_out_of_its_place_and_a_file_not_whole_are_refused(tmp_path: Path) -> None:
    service, _, _ = new_service(tmp_path)
    upload, _ = service.start("Berserk.cbz", 15)

    with pytest.raises(ChunkRefusedError):
        service.receive(upload.id, 2, b"x")
    with pytest.raises(ChunkRefusedError):
        service.receive(upload.id, 0, b"short")
    with pytest.raises(ChunkRefusedError):
        service.finish(upload.id, "0" * 64)
    with pytest.raises(UploadNotFoundError):
        service.receive(99, 0, b"x")
