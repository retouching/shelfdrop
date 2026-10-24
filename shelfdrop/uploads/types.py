"""Types of the uploads: a file sent in chunks from the page Manuel."""

from dataclasses import dataclass
from typing import Final, Literal

type UploadState = Literal["receiving", "verified", "listed", "corrupt", "lost"]
# Why an upload is refused at its start: its type, its size, its name.
type Refusal = Literal["type", "size", "name"]

# The files the page sends: books, comics, audiobooks, and a ZIP of them.
UPLOAD_EXTENSIONS: Final = frozenset({".epub", ".pdf", ".cbz", ".cbr", ".m4b", ".mp3", ".zip"})
MIB: Final = 1024 * 1024


@dataclass(frozen=True, kw_only=True)
class Upload:
    """A file sent in chunks, as `uploads` keeps it."""

    id: int
    name: str
    size: int
    chunk_size: int
    received: tuple[int, ...]
    sha256: str | None
    state: UploadState
    created_at: int
    updated_at: int


@dataclass(frozen=True, kw_only=True)
class UploadOptions:
    # A chunk: under the 100 MB a request through some reverse proxies may hold.
    chunk_bytes: int = 50 * MIB
    # A file: 5 GiB at most.
    max_bytes: int = 5 * 1024 * MIB


def chunk_count(size: int, chunk_bytes: int) -> int:
    """The chunks of a file of `size` bytes."""
    return max(1, -(-size // chunk_bytes))


def chunk_length(size: int, chunk_bytes: int, index: int) -> int:
    """The length chunk `index` must have: `chunk_bytes`, but the last one."""
    return min(chunk_bytes, size - index * chunk_bytes)
