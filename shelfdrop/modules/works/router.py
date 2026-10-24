"""The routes of the work search (ADR 0007): async, the only ones, since a search waits on
every metadata source at once."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.modules.works.errors import (
    merge_not_found,
    merge_refused,
    query_too_short,
    sources_unavailable,
    work_cover_not_found,
    work_not_found,
)
from shelfdrop.modules.works.schemas import (
    WorkMergeCreate,
    WorkMergeRead,
    WorkRead,
    WorkSearchRead,
)
from shelfdrop.utils.pictures import picture_of
from shelfdrop.works.covers import WorkCovers
from shelfdrop.works.exceptions import (
    MergeNotFoundError,
    MergeRefusedError,
    NoSourceAnsweredError,
    QueryTooShortError,
    WorkNotFoundError,
)
from shelfdrop.works.service import WorkService
from shelfdrop.works.types import Kind

router = APIRouter(prefix="/v1/works", tags=["works"], route_class=WireupRoute)


@router.get("")
async def search_works(
    service: Injected[WorkService],
    q: Annotated[str, Query(min_length=1, max_length=200)],
    kind: Kind = "manga",
    retry: bool = False,
) -> WorkSearchRead:
    """`retry`: the sources resting after their failures are asked too (the button Réessayer)."""
    try:
        found = await service.search(q, kind, retry=retry)
    except QueryTooShortError as exc:
        raise query_too_short() from exc
    except NoSourceAnsweredError as exc:
        raise sources_unavailable() from exc
    return WorkSearchRead.model_validate(found)


@router.post("/merges", status_code=status.HTTP_201_CREATED)
async def merge_works(service: Injected[WorkService], body: WorkMergeCreate) -> WorkMergeRead:
    try:
        merged = await service.merge_works(body.kind, body.work_ids, body.shelf_name)
    except WorkNotFoundError as exc:
        raise work_not_found() from exc
    except MergeRefusedError as exc:
        raise merge_refused() from exc
    return WorkMergeRead.model_validate(merged)


@router.delete("/merges/{merge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def split_works(service: Injected[WorkService], merge_id: int) -> None:
    try:
        await service.split_works(merge_id)
    except MergeNotFoundError as exc:
        raise merge_not_found() from exc


@router.get("/cover")
async def read_work_cover(
    covers: Injected[WorkCovers], work_id: Annotated[str, Query(alias="id", min_length=1)]
) -> Response:
    """The cover of a work kept from a search (7 days), read at its source by the API so that
    the page loads no picture from another site. In the query, since an id may hold slashes
    (`bnf:http://...`)."""
    data = await covers.cover(work_id)
    found = None if data is None else picture_of(data)
    if data is None or found is None:
        raise work_cover_not_found()
    return Response(
        content=data, media_type=found[1], headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get("/{work_id}")
async def read_work(service: Injected[WorkService], work_id: str) -> WorkRead:
    try:
        work = await service.read_work(work_id)
    except WorkNotFoundError as exc:
        raise work_not_found() from exc
    return WorkRead.model_validate(work)
