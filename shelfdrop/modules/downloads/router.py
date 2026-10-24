"""The routes of the downloads: send releases to qBittorrent, read the downloads with the figures
of qBittorrent, send one again, the cover of the work of one. Async: their service holds the
async clients of qBittorrent."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.auth.types import Account
from shelfdrop.downloads.exceptions import (
    DownloadNotFoundError,
    NotAutomaticError,
    NotRetryableError,
    UnknownReleasesError,
)
from shelfdrop.downloads.service import DownloadService
from shelfdrop.downloads.types import Choice, DownloadView, SendOrder
from shelfdrop.http.dependencies import require_access
from shelfdrop.modules.downloads.errors import (
    download_cover_not_found,
    download_not_found,
    download_not_retryable,
    release_not_automatic,
    release_not_in_search,
    search_not_found,
)
from shelfdrop.modules.downloads.schemas import (
    DownloadRead,
    DownloadsCreate,
    DownloadsRead,
    ProgressRead,
    VolumesBody,
)
from shelfdrop.releases.exceptions import SearchNotFoundError
from shelfdrop.releases.types import Volumes

router = APIRouter(prefix="/v1/downloads", tags=["downloads"], route_class=WireupRoute)


def download_read(view: DownloadView) -> DownloadRead:
    download = view.download
    return DownloadRead(
        id=download.id,
        title=download.title,
        indexer=download.indexer,
        size=download.size,
        info_hash=download.info_hash,
        mode=download.mode,
        kind=download.kind,
        category=download.category,
        work_id=download.work_id,
        work_name=download.work_name,
        author=download.author,
        series=download.series,
        volumes=VolumesBody.model_validate(download.volumes),
        progress=ProgressRead.model_validate(view.progress),
        attempts=download.attempts,
        created_at=download.created_at,
        created_by=download.created_by,
    )


@router.get("")
async def read_downloads(service: Injected[DownloadService]) -> DownloadsRead:
    return DownloadsRead(downloads=[download_read(v) for v in await service.read()])


@router.post("")
async def send_downloads(
    service: Injected[DownloadService],
    account: Annotated[Account, Depends(require_access)],
    body: DownloadsCreate,
) -> DownloadsRead:
    order = SendOrder(
        search_id=body.search_id,
        work_id=body.work_id,
        author=body.author.strip(),
        series=body.series.strip(),
        choices=tuple(
            Choice(
                release_id=r.id,
                volumes=Volumes(kind=r.volumes.kind, first=r.volumes.first, last=r.volumes.last),
            )
            for r in body.releases
        ),
    )
    try:
        views = await service.send(order, account.username)
    except SearchNotFoundError as exc:
        raise search_not_found() from exc
    except UnknownReleasesError as exc:
        raise release_not_in_search(exc.ids) from exc
    except NotAutomaticError as exc:
        raise release_not_automatic(exc.ids) from exc
    return DownloadsRead(downloads=[download_read(v) for v in views])


@router.post("/{download_id}/retry")
async def retry_download(service: Injected[DownloadService], download_id: int) -> DownloadRead:
    try:
        return download_read(await service.retry(download_id))
    except DownloadNotFoundError as exc:
        raise download_not_found() from exc
    except NotRetryableError as exc:
        raise download_not_retryable() from exc


@router.get("/{download_id}/cover")
async def read_download_cover(service: Injected[DownloadService], download_id: int) -> Response:
    """The cover of the work of an automatic download, for the page: read by the API at the
    sources of the work, kept a while in memory."""
    try:
        found = await service.cover(download_id)
    except DownloadNotFoundError as exc:
        raise download_not_found() from exc
    if found is None:
        raise download_cover_not_found()
    data, content_type = found
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"}
    )
