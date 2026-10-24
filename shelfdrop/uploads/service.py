"""UploadService: a file sent from the page Manuel in chunks of 50 MiB:
started (or resumed, the same file still receiving), its chunks written as they come, then put
together and checked against the SHA-256 the page read from the file. A file checked waits in
the data directory for the placement worker, which moves it into Ranger
(`shelfdrop.placement.byhand`). Runs in the threadpool: the routes are sync."""

import logging
from pathlib import PurePath
from typing import Protocol

from shelfdrop.journal.types import NewEvent
from shelfdrop.uploads.exceptions import (
    ChunkRefusedError,
    UploadCorruptError,
    UploadDoneError,
    UploadNotFoundError,
    UploadRefusedError,
)
from shelfdrop.uploads.repository import UploadRepository
from shelfdrop.uploads.store import UploadStore
from shelfdrop.uploads.types import (
    UPLOAD_EXTENSIONS,
    Upload,
    UploadOptions,
    chunk_count,
    chunk_length,
)
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)

# The longest name of a file sent.
MAX_NAME = 200
# The type of a file sent, as the journal names it.
TYPES = {
    ".epub": "EPUB",
    ".pdf": "PDF",
    ".cbz": "CBZ",
    ".cbr": "CBR",
    ".m4b": "M4B",
    ".mp3": "MP3",
    ".zip": "ZIP",
}


class UploadEvents(Protocol):
    def record(self, event: NewEvent) -> None: ...


def clean_name(name: str) -> str:
    """The file name alone, its spaces tidied. Raises UploadRefusedError."""
    cleaned = " ".join(PurePath(name.replace("\\", "/")).name.split())
    if not cleaned or cleaned.startswith(".") or len(cleaned) > MAX_NAME:
        raise UploadRefusedError("name")
    if PurePath(cleaned).suffix.lower() not in UPLOAD_EXTENSIONS:
        raise UploadRefusedError("type")
    return cleaned


class UploadService:
    def __init__(
        self,
        repository: UploadRepository,
        store: UploadStore,
        events: UploadEvents,
        options: UploadOptions,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.store = store
        self.events = events
        self.options = options
        self.clock = clock

    def start(self, name: str, size: int) -> tuple[Upload, bool]:
        """The upload of the file `name` of `size` bytes, and whether it is new: the same file
        still receiving its chunks is resumed. Raises UploadRefusedError."""
        cleaned = clean_name(name)
        if not 0 < size <= self.options.max_bytes:
            raise UploadRefusedError("size")
        chunk = self.options.chunk_bytes
        found = self.repository.find_receiving(cleaned, size, chunk)
        if found is not None:
            return found, False
        upload = self.repository.add(cleaned, size, chunk, int(self.clock.now()))
        self.repository.commit()
        logger.info("Upload started", extra={"upload": upload.id, "size": size})
        return upload, True

    def receive(self, upload_id: int, index: int, data: bytes) -> Upload:
        """Chunk `index` of the upload kept. Raises UploadNotFoundError, UploadDoneError,
        ChunkRefusedError."""
        upload = self.receiving(upload_id)
        count = chunk_count(upload.size, upload.chunk_size)
        if not 0 <= index < count or len(data) != chunk_length(
            upload.size, upload.chunk_size, index
        ):
            raise ChunkRefusedError
        self.store.write_chunk(upload_id, index, data)
        received = sorted({*upload.received, index})
        self.repository.mark_received(upload_id, received, int(self.clock.now()))
        self.repository.commit()
        return self.read(upload_id)

    def finish(self, upload_id: int, sha256: str) -> Upload:
        """The chunks put together and checked against `sha256`: a file checked waits for the
        worker, a corrupt one is removed. Raises UploadNotFoundError, UploadDoneError,
        ChunkRefusedError (chunks missing), UploadCorruptError."""
        upload = self.receiving(upload_id)
        count = chunk_count(upload.size, upload.chunk_size)
        if len(upload.received) != count:
            raise ChunkRefusedError
        digest = self.store.put_together(upload_id, upload.name, count)
        now = int(self.clock.now())
        if digest != sha256.lower():
            self.store.remove(upload_id)
            self.repository.mark(upload_id, "corrupt", now)
            self.repository.commit()
            logger.info("Upload corrupt", extra={"upload": upload_id})
            self.events.record(
                NewEvent(
                    type="failed",
                    group=f"failed:upload:{upload_id}",
                    facts={"what": "upload_corrupt", "release": upload.name, "error": "SHA-256"},
                )
            )
            raise UploadCorruptError
        self.repository.mark(upload_id, "verified", now, digest)
        self.repository.commit()
        logger.info("Upload checked", extra={"upload": upload_id, "size": upload.size})
        self.events.record(
            NewEvent(
                type="uploaded",
                group=f"uploaded:{upload_id}",
                facts={
                    "file": upload.name,
                    "size": upload.size,
                    "type": TYPES.get(PurePath(upload.name).suffix.lower(), ""),
                },
            )
        )
        return self.read(upload_id)

    def receiving(self, upload_id: int) -> Upload:
        upload = self.read(upload_id)
        if upload.state != "receiving":
            raise UploadDoneError
        return upload

    def read(self, upload_id: int) -> Upload:
        upload = self.repository.read(upload_id)
        if upload is None:
            raise UploadNotFoundError
        return upload
