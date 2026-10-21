"""The routes of the release search: async, since a search runs on the event loop and its
progress is streamed (Server-Sent Events)."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.modules.searches.errors import (
    prowlarr_unavailable,
    query_too_short,
    search_not_found,
    too_many_names,
)
from shelfdrop.modules.searches.schemas import (
    ReleaseSearchRead,
    SearchCreate,
    SearchProgressRead,
)
from shelfdrop.releases.exceptions import ProwlarrError, SearchNotFoundError, TooManyNamesError
from shelfdrop.releases.service import ReleaseService
from shelfdrop.works.exceptions import QueryTooShortError

router = APIRouter(prefix="/v1/searches", tags=["searches"], route_class=WireupRoute)


@router.post("")
async def start_search(service: Injected[ReleaseService], body: SearchCreate) -> SearchProgressRead:
    try:
        progress = await service.start(
            mode=body.mode,
            kind=body.kind,
            title=body.title,
            names=body.names,
            refresh=body.refresh,
        )
    except QueryTooShortError as exc:
        raise query_too_short() from exc
    except TooManyNamesError as exc:
        raise too_many_names() from exc
    except ProwlarrError as exc:
        raise prowlarr_unavailable() from exc
    return SearchProgressRead.model_validate(progress)


@router.get("/{search_id}")
async def read_search(service: Injected[ReleaseService], search_id: str) -> ReleaseSearchRead:
    try:
        found = await service.read(search_id)
    except SearchNotFoundError as exc:
        raise search_not_found() from exc
    return ReleaseSearchRead.model_validate(found)


@router.get("/{search_id}/events", response_class=StreamingResponse)
async def follow_search(service: Injected[ReleaseService], search_id: str) -> StreamingResponse:
    """The progress at each change, as `progress` events, then an `end` event."""
    try:
        updates = service.watch(search_id)
    except SearchNotFoundError as exc:
        raise search_not_found() from exc

    async def events() -> AsyncIterator[str]:
        async for progress in updates:
            data = SearchProgressRead.model_validate(progress).model_dump(mode="json")
            yield f"event: progress\ndata: {json.dumps(data)}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
