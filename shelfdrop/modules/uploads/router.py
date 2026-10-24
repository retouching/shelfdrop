"""The routes of the uploads of the page Manuel: sync, the chunks are
written by the threadpool."""

from typing import Annotated

from fastapi import APIRouter, Body, Response, status
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.modules.uploads.errors import (
    chunk_refused,
    upload_corrupt,
    upload_done,
    upload_not_found,
    upload_refused,
)
from shelfdrop.modules.uploads.schemas import UploadCreate, UploadFinish, UploadRead
from shelfdrop.uploads.exceptions import (
    ChunkRefusedError,
    UploadCorruptError,
    UploadDoneError,
    UploadNotFoundError,
    UploadRefusedError,
)
from shelfdrop.uploads.service import UploadService
from shelfdrop.uploads.types import Upload, chunk_count

router = APIRouter(prefix="/v1/uploads", tags=["uploads"], route_class=WireupRoute)


def upload_read(upload: Upload) -> UploadRead:
    return UploadRead(
        id=upload.id,
        name=upload.name,
        size=upload.size,
        chunk_size=upload.chunk_size,
        chunks=chunk_count(upload.size, upload.chunk_size),
        received=list(upload.received),
        state=upload.state,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def start_upload(
    body: UploadCreate, response: Response, service: Injected[UploadService]
) -> UploadRead:
    try:
        upload, new = service.start(body.name, body.size)
    except UploadRefusedError as exc:
        raise upload_refused(exc.reason) from exc
    if not new:
        response.status_code = status.HTTP_200_OK
    return upload_read(upload)


@router.put("/{upload_id}/chunks/{index}")
def receive_chunk(
    upload_id: int,
    index: int,
    data: Annotated[bytes, Body(media_type="application/octet-stream")],
    service: Injected[UploadService],
) -> UploadRead:
    try:
        upload = service.receive(upload_id, index, data)
    except UploadNotFoundError as exc:
        raise upload_not_found() from exc
    except UploadDoneError as exc:
        raise upload_done() from exc
    except ChunkRefusedError as exc:
        raise chunk_refused() from exc
    return upload_read(upload)


@router.post("/{upload_id}/finish")
def finish_upload(
    upload_id: int, body: UploadFinish, service: Injected[UploadService]
) -> UploadRead:
    try:
        upload = service.finish(upload_id, body.sha256)
    except UploadNotFoundError as exc:
        raise upload_not_found() from exc
    except UploadDoneError as exc:
        raise upload_done() from exc
    except ChunkRefusedError as exc:
        raise chunk_refused() from exc
    except UploadCorruptError as exc:
        raise upload_corrupt() from exc
    return upload_read(upload)
