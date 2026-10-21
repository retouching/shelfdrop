"""UploadStore: the chunks of the uploads and the files put together from them, in the folder
`uploads/` of the data directory (its volume, writable by the API and read by the placement
worker). Nothing else is written there."""

import hashlib
import shutil
from pathlib import Path
from typing import Final

# The chunks of an upload, in a folder of its own.
CHUNKS: Final = "chunks"
READ_BYTES: Final = 1024 * 1024


class UploadStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def folder(self, upload_id: int) -> Path:
        return self.root / str(upload_id)

    def file(self, upload_id: int, name: str) -> Path:
        """The file put together, once checked."""
        return self.folder(upload_id) / name

    def chunk(self, upload_id: int, index: int) -> Path:
        return self.folder(upload_id) / CHUNKS / f"{index:05d}"

    def write_chunk(self, upload_id: int, index: int, data: bytes) -> None:
        """Chunk `index` written through a `.part`: a cut request leaves no half chunk."""
        target = self.chunk(upload_id, index)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        part.write_bytes(data)
        part.replace(target)

    def put_together(self, upload_id: int, name: str, count: int) -> str:
        """The `count` chunks joined into the file `name`, through a `.part`; the chunks
        removed. Returns its SHA-256 (hex)."""
        target = self.file(upload_id, name)
        part = target.with_name(target.name + ".part")
        digest = hashlib.sha256()
        with part.open("wb") as out:
            for index in range(count):
                with self.chunk(upload_id, index).open("rb") as chunk:
                    while block := chunk.read(READ_BYTES):
                        digest.update(block)
                        out.write(block)
        part.replace(target)
        shutil.rmtree(self.folder(upload_id) / CHUNKS, ignore_errors=True)
        return digest.hexdigest()

    def remove(self, upload_id: int) -> None:
        shutil.rmtree(self.folder(upload_id), ignore_errors=True)

    def upload_ids(self) -> list[int]:
        """The uploads that have a folder here."""
        if not self.root.is_dir():
            return []
        return sorted(int(p.name) for p in self.root.iterdir() if p.is_dir() and p.name.isdigit())
