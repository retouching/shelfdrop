"""The routes of the waiting searches (the page En attente of Rechercher): the list, the
additions, a search now, a removal, and the volumes already on the shelf."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import require_access
from shelfdrop.modules.waiting.errors import waiting_not_found
from shelfdrop.modules.waiting.schemas import (
    OwnedRead,
    WaitingAdded,
    WaitingCreate,
    WaitingRead,
    WaitingsRead,
    WantedBody,
)
from shelfdrop.waiting.exceptions import WaitingNotFoundError
from shelfdrop.waiting.matching import label
from shelfdrop.waiting.service import WaitingService, WaitingSettings
from shelfdrop.waiting.types import WaitingView, WaitOrder, Wanted
from shelfdrop.works.types import Kind

router = APIRouter(prefix="/v1/waiting", tags=["waiting"], route_class=WireupRoute)


def waiting_read(view: WaitingView) -> WaitingRead:
    waiting = view.waiting
    return WaitingRead(
        id=waiting.id,
        work_id=waiting.work_id,
        title=waiting.title,
        author=waiting.author,
        kind=waiting.kind,
        names=list(waiting.names),
        wanted=WantedBody(
            target=waiting.wanted.target,
            volume=waiting.wanted.volume,
            chapter_from=waiting.wanted.chapter_from,
            chapter_to=waiting.wanted.chapter_to,
        ),
        label=label(waiting.wanted),
        state=waiting.state,
        releases=waiting.releases,
        attempts=waiting.attempts,
        created_at=waiting.created_at,
        created_by=waiting.created_by,
        searched_at=waiting.searched_at,
        next_search_at=view.next_search_at,
    )


@router.get("")
async def read_waiting(
    service: Injected[WaitingService], settings: Injected[WaitingSettings]
) -> WaitingsRead:
    views = await service.read()
    every = await settings.waiting_seconds()
    return WaitingsRead(searches=[waiting_read(v) for v in views], every_hours=every // 3600)


@router.post("")
async def add_waiting(
    body: WaitingCreate,
    service: Injected[WaitingService],
    account: Annotated[Account, Depends(require_access)],
) -> WaitingAdded:
    order = WaitOrder(
        work_id=body.work_id,
        title=body.title.strip(),
        author=body.author.strip(),
        kind=body.kind,
        names=tuple(dict.fromkeys(n.strip() for n in body.names if n.strip())),
        wanted=tuple(
            Wanted(
                target=w.target,
                volume=w.volume if w.target == "volume" else None,
                chapter_from=w.chapter_from if w.target == "chapters" else None,
                chapter_to=w.chapter_to if w.target == "chapters" else None,
            )
            for w in body.wanted
        ),
        created_by=account.username,
    )
    added, skipped = await service.add(order)
    return WaitingAdded(added=[waiting_read(v) for v in added], skipped=skipped)


@router.post("/{waiting_id}/search")
async def search_now(waiting_id: int, service: Injected[WaitingService]) -> WaitingRead:
    try:
        return waiting_read(await service.search(waiting_id))
    except WaitingNotFoundError as exc:
        raise waiting_not_found() from exc


@router.delete("/{waiting_id}", status_code=204)
async def remove_waiting(waiting_id: int, service: Injected[WaitingService]) -> Response:
    try:
        await service.remove(waiting_id)
    except WaitingNotFoundError as exc:
        raise waiting_not_found() from exc
    return Response(status_code=204)


@router.get("/owned")
async def read_owned(
    service: Injected[WaitingService],
    kind: Kind,
    title: Annotated[str, Query(min_length=1, max_length=300)],
    work_id: Annotated[str | None, Query(max_length=300)] = None,
) -> OwnedRead:
    return OwnedRead(volumes=await service.owned(kind, title, work_id))
