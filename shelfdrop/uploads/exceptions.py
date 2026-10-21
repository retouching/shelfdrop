"""Exceptions of the uploads."""

from shelfdrop.uploads.types import Refusal


class UploadRefusedError(ValueError):
    """A file the page cannot send: its type, its size or its name."""

    def __init__(self, reason: Refusal) -> None:
        super().__init__(reason)
        self.reason: Refusal = reason


class UploadNotFoundError(Exception):
    """No upload with this id."""


class UploadDoneError(Exception):
    """The upload is received already (checked, or listed in Ranger), or refused as corrupt."""


class ChunkRefusedError(ValueError):
    """A chunk out of the file, of another length than its place asks, or a file whose chunks
    are not all there."""


class UploadCorruptError(Exception):
    """The file put together from its chunks has another SHA-256 than the page gave."""
