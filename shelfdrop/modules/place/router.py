"""The routes of the page Ranger: the files to place, a file linked to a work (or a release in
chapters to its volumes), a file of the shelf corrected, and the scan of the libraries."""

from fastapi import APIRouter, Query, status
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.modules.place.errors import item_busy, item_not_found, request_refused
from shelfdrop.modules.place.schemas import (
    ChapterBody,
    ChaptersBody,
    ItemRead,
    ItemsRead,
    PlaceBody,
    VolumeBody,
)
from shelfdrop.placement.paths import SEPARATOR
from shelfdrop.placement.types import (
    LIBRARY_NAMES,
    ChapterRequest,
    ChaptersRequest,
    PlaceItem,
    PlaceRequest,
    ShelfFile,
    VolumeRange,
    VolumeRequest,
)
from shelfdrop.ranger.exceptions import ItemBusyError, ItemNotFoundError, RequestRefusedError
from shelfdrop.ranger.service import RangerService

router = APIRouter(prefix="/v1/place", tags=["place"], route_class=WireupRoute)


def item_read(item: PlaceItem) -> ItemRead:
    return ItemRead(
        id=f"item-{item.id}",
        origin=item.origin,
        kind=item.kind,
        name=item.name,
        path=item.path,
        size=item.size,
        state="placing" if item.request is not None else item.state,
        reason=item.reason,
        error=item.error,
        destination=item.destination,
        chapters=list(item.chapters),
        existing=list(item.existing),
        loose=list(item.loose),
        series=item.series,
        author=item.author,
        work_id=item.work_id,
    )


def shelved_read(shelved: ShelfFile) -> ItemRead:
    return ItemRead(
        id=f"shelf-{shelved.id}",
        origin="library",
        kind=shelved.kind,
        name=shelved.path.rsplit("/", 1)[-1],
        path=shelved.path,
        size=0,
        state="placed",
        reason=None,
        error=None,
        destination=f"{LIBRARY_NAMES[shelved.kind]}{SEPARATOR}{shelved.series}",
        chapters=[],
        existing=[],
        loose=[],
        series=shelved.series,
        author=shelved.author,
        work_id=shelved.work_id,
    )


def volume_request(body: VolumeBody) -> VolumeRequest:
    return VolumeRequest(
        kind=body.kind,
        work_id=body.work_id,
        series=body.series,
        author=body.author,
        volume=body.volume,
        title=body.title,
    )


def request_of(body: VolumeBody | ChapterBody | ChaptersBody) -> PlaceRequest:
    match body:
        case VolumeBody():
            return volume_request(body)
        case ChapterBody():
            return ChapterRequest(
                work_id=body.work_id,
                series=body.series,
                author=body.author,
                first=body.first,
                last=body.last,
                volume=body.volume,
            )
        case ChaptersBody():
            return ChaptersRequest(
                work_id=body.work_id,
                series=body.series,
                author=body.author,
                summary=body.summary,
                volumes=tuple(
                    VolumeRange(volume=v.volume, first=v.first, last=v.last, replace=v.replace)
                    for v in body.volumes
                ),
                rest=body.rest,
            )


@router.get("/items")
async def read_items(
    service: Injected[RangerService], q: str = Query(default="", max_length=200)
) -> ItemsRead:
    listing = await service.read(q)
    count = await service.count()
    return ItemsRead(
        items=[item_read(i) for i in listing.items] + [shelved_read(s) for s in listing.shelved],
        open=count,
    )


@router.post("/items/{item_id}/link", status_code=status.HTTP_202_ACCEPTED)
async def link_item(item_id: int, body: PlaceBody, service: Injected[RangerService]) -> ItemRead:
    try:
        item = await service.link(item_id, request_of(body))
    except ItemNotFoundError as exc:
        raise item_not_found() from exc
    except ItemBusyError as exc:
        raise item_busy() from exc
    except RequestRefusedError as exc:
        raise request_refused() from exc
    return item_read(item)


@router.post("/shelf/{file_id}/link", status_code=status.HTTP_202_ACCEPTED)
async def relink_file(file_id: int, body: VolumeBody, service: Injected[RangerService]) -> ItemRead:
    try:
        item = await service.relink(file_id, volume_request(body))
    except ItemNotFoundError as exc:
        raise item_not_found() from exc
    return item_read(item)


@router.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def scan(service: Injected[RangerService]) -> None:
    await service.scan()
