"""The routes of the trackers: the indexers of Prowlarr, which are asked, in which order. Async,
as every route of the release search (ADR 0011)."""

from fastapi import APIRouter
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.modules.trackers.errors import prowlarr_unavailable
from shelfdrop.modules.trackers.schemas import TrackerRead, TrackersRead, TrackersUpdate
from shelfdrop.releases.exceptions import ProwlarrError
from shelfdrop.releases.service import ReleaseService
from shelfdrop.releases.types import Tracker

router = APIRouter(prefix="/v1/trackers", tags=["trackers"], route_class=WireupRoute)


def trackers_read(trackers: list[Tracker]) -> TrackersRead:
    return TrackersRead(trackers=[TrackerRead.model_validate(t) for t in trackers])


@router.get("")
async def read_trackers(service: Injected[ReleaseService]) -> TrackersRead:
    return trackers_read(await service.read_trackers())


@router.post("/refresh")
async def refresh_trackers(service: Injected[ReleaseService]) -> TrackersRead:
    """Read the indexers of Prowlarr again."""
    try:
        return trackers_read(await service.refresh_trackers())
    except ProwlarrError as exc:
        raise prowlarr_unavailable() from exc


@router.put("")
async def save_trackers(service: Injected[ReleaseService], body: TrackersUpdate) -> TrackersRead:
    choices = [(c.indexer_id, c.used, c.auto) for c in body.trackers]
    return trackers_read(await service.save_trackers(choices))
