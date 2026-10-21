"""Request and response schemas of the uploads module."""

from pydantic import BaseModel, ConfigDict, Field

from shelfdrop.uploads.types import UploadState


class UploadCreate(BaseModel):
    # The name of the file, its size in bytes.
    name: str = Field(min_length=1, max_length=300)
    size: int = Field(ge=0)


class UploadFinish(BaseModel):
    # The SHA-256 of the whole file, as the page read it (hex).
    sha256: str = Field(pattern=r"^[0-9A-Fa-f]{64}$")


class UploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # The name kept (the file name alone).
    name: str
    size: int
    # Every chunk is this long, but the last one.
    chunk_size: int
    chunks: int
    # The indexes of the chunks received: the page sends the others.
    received: list[int]
    # `receiving`, then `verified` (waiting for the worker), `listed` (in Ranger).
    state: UploadState
