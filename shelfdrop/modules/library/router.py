"""The routes of the page Jellyfin: the series of the libraries of Jellyfin, their volumes,
their files, their images, what the sources propose, their changes, the summaries by batch,
the scans and the sync of the metadata."""

import base64
from typing import Final
from urllib.parse import quote

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.library.exceptions import (
    ImageRefusedError,
    LibraryUnavailableError,
    SeriesNotFoundError,
    VolumeNotFoundError,
)
from shelfdrop.library.service import LibraryService
from shelfdrop.library.sync import LibrarySync
from shelfdrop.library.types import (
    ImageChoice,
    ItemImage,
    LinkImage,
    ScanOrder,
    SentImage,
    SeriesChange,
    VolumeChange,
)
from shelfdrop.modules.library.errors import (
    image_refused,
    jellyfin_unavailable,
    series_not_found,
    volume_not_found,
)
from shelfdrop.modules.library.schemas import (
    FilledRead,
    ImageBody,
    LibraryRead,
    ProposalsRead,
    ScanBody,
    ScanRead,
    SeriesChangeBody,
    SeriesRead,
    SummariesBody,
    SyncBody,
    SyncRead,
    VolumeChangeBody,
    VolumeRead,
    VolumesRead,
)

router = APIRouter(prefix="/v1/library", tags=["library"], route_class=WireupRoute)

# The characters a quoted file name keeps in the fallback `filename=` of a download.
PLAIN: Final = frozenset(chr(c) for c in range(0x20, 0x7F)) - {'"', "\\"}


def attachment(name: str) -> str:
    """The `Content-Disposition` of a file: its name in ASCII, and whole in UTF-8 (RFC 6266,
    RFC 5987)."""
    fallback = "".join(c if c in PLAIN else "_" for c in name) or "file"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def image_of(body: ImageBody | None) -> ImageChoice | None:
    if body is None:
        return None
    if body.kind == "item" and body.item_id:
        return ItemImage(item_id=body.item_id)
    if body.kind == "url" and body.url:
        return LinkImage(url=body.url)
    if body.kind == "data" and body.data:
        return SentImage(data=base64.b64decode(body.data))
    raise image_refused()


@router.get("/series")
async def read_series(service: Injected[LibraryService]) -> LibraryRead:
    try:
        found = await service.read()
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc
    return LibraryRead(series=[SeriesRead.model_validate(s) for s in found])


@router.get("/series/{series_id}/proposals")
async def read_proposals(series_id: str, service: Injected[LibraryService]) -> ProposalsRead:
    try:
        return ProposalsRead.model_validate(await service.proposals(series_id))
    except SeriesNotFoundError as exc:
        raise series_not_found() from exc
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.put("/series/{series_id}")
async def change_series(
    series_id: str, body: SeriesChangeBody, service: Injected[LibraryService]
) -> SeriesRead:
    change = SeriesChange(
        name=body.name.strip(),
        original_title=body.original_title.strip(),
        authors=tuple(a.strip() for a in body.authors if a.strip()),
        year=body.year,
        genres=tuple(g.strip() for g in body.genres if g.strip()),
        summary=body.summary.strip(),
        lock=body.lock,
        summary_to_volumes=body.summary_to_volumes,
        image=image_of(body.image),
        image_to_series=body.image_to_series,
        image_to_volumes=body.image_to_volumes,
        save_cover=body.save_cover,
    )
    try:
        return SeriesRead.model_validate(await service.change(series_id, change))
    except SeriesNotFoundError as exc:
        raise series_not_found() from exc
    except ImageRefusedError as exc:
        raise image_refused() from exc
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.get("/series/{series_id}/volumes")
async def read_volumes(series_id: str, service: Injected[LibraryService]) -> VolumesRead:
    try:
        return VolumesRead.model_validate(await service.volumes(series_id))
    except SeriesNotFoundError as exc:
        raise series_not_found() from exc
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.get(
    "/items/{item_id}/file",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def read_file(item_id: str, service: Injected[LibraryService]) -> StreamingResponse:
    """The file of a book or an audiobook, as Jellyfin sends it (`/Items/{id}/Download`)."""
    try:
        found = await service.download(item_id)
    except VolumeNotFoundError as exc:
        raise volume_not_found() from exc
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc
    headers = {"Content-Disposition": attachment(found.name)}
    if found.file.size is not None:
        headers["Content-Length"] = str(found.file.size)
    return StreamingResponse(
        found.file.chunks,
        media_type=found.file.content_type,
        headers=headers,
        background=BackgroundTask(found.file.close),
    )


@router.put("/items/{item_id}")
async def change_volume(
    item_id: str, body: VolumeChangeBody, service: Injected[LibraryService]
) -> VolumeRead:
    change = VolumeChange(
        name=body.name.strip(),
        number=body.number,
        summary=body.summary.strip(),
        authors=tuple(a.strip() for a in body.authors if a.strip()),
        lock=body.lock,
        image=image_of(body.image),
    )
    try:
        return VolumeRead.model_validate(await service.change_volume(item_id, change))
    except VolumeNotFoundError as exc:
        raise volume_not_found() from exc
    except ImageRefusedError as exc:
        raise image_refused() from exc
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.get("/items/{item_id}/image")
async def read_image(
    item_id: str,
    service: Injected[LibraryService],
    width: int = Query(default=400, ge=50, le=2000),
) -> Response:
    """The image Jellyfin holds for a series or a volume, for the page (the session of the
    page is asked; Jellyfin is not reachable from the browser)."""
    try:
        data, content_type = await service.image(item_id, width)
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=300"}
    )


@router.post("/summaries")
async def fill_summaries(body: SummariesBody, service: Injected[LibraryService]) -> FilledRead:
    try:
        return FilledRead(series=await service.fill(body.summaries))
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.post("/scan", status_code=202)
async def scan(body: ScanBody, service: Injected[LibraryService]) -> ScanRead:
    try:
        await service.scan(ScanOrder(mode=body.mode, kind=body.kind, series_id=body.series_id))
        return ScanRead(progress=await service.scanning())
    except SeriesNotFoundError as exc:
        raise series_not_found() from exc
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.get("/scan")
async def read_scan(service: Injected[LibraryService]) -> ScanRead:
    try:
        return ScanRead(progress=await service.scanning())
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.post("/sync", status_code=202)
async def start_sync(body: SyncBody, sync: Injected[LibrarySync]) -> SyncRead:
    """The metadata of the files placed sent again to Jellyfin, in the background; while a
    sync runs, its state alone."""
    try:
        return SyncRead.model_validate(await sync.start(body.series_id))
    except SeriesNotFoundError as exc:
        raise series_not_found() from exc
    except LibraryUnavailableError as exc:
        raise jellyfin_unavailable() from exc


@router.get("/sync")
async def read_sync(sync: Injected[LibrarySync]) -> SyncRead:
    return SyncRead.model_validate(sync.state())
