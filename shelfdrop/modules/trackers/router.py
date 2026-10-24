"""The routes of the trackers: the indexers of Prowlarr, which are asked, in which order, in which
categories for each kind. Async, as every route of the release search (ADR 0011)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import require_session
from shelfdrop.modules.trackers.errors import prowlarr_unavailable, unknown_tracker_category
from shelfdrop.modules.trackers.schemas import (
    CategoryRead,
    KindCategories,
    TrackerRead,
    TrackersRead,
    TrackersUpdate,
)
from shelfdrop.releases.exceptions import ProwlarrError, UnknownCategoryError
from shelfdrop.releases.service import ReleaseService
from shelfdrop.releases.types import DEFAULT_CATEGORIES, Tracker, TrackerChoice

router = APIRouter(prefix="/v1/trackers", tags=["trackers"], route_class=WireupRoute)


def tracker_read(tracker: Tracker) -> TrackerRead:
    chosen = tracker.chosen or {}
    return TrackerRead(
        indexer_id=tracker.indexer_id,
        name=tracker.name,
        language=tracker.language,
        prowlarr_enabled=tracker.prowlarr_enabled,
        used=tracker.used,
        auto=tracker.auto,
        available_categories=[CategoryRead.model_validate(c) for c in tracker.available],
        categories=KindCategories(
            manga=list(chosen.get("manga", DEFAULT_CATEGORIES["manga"])),
            ebook=list(chosen.get("ebook", DEFAULT_CATEGORIES["ebook"])),
            audiobook=list(chosen.get("audiobook", DEFAULT_CATEGORIES["audiobook"])),
        ),
        default_categories=tracker.chosen is None,
    )


def trackers_read(trackers: list[Tracker]) -> TrackersRead:
    return TrackersRead(trackers=[tracker_read(t) for t in trackers])


@router.get("")
async def read_trackers(service: Injected[ReleaseService]) -> TrackersRead:
    return trackers_read(await service.read_trackers())


@router.post("/refresh")
async def refresh_trackers(service: Injected[ReleaseService]) -> TrackersRead:
    """Read the indexers of Prowlarr again, their categories with them."""
    try:
        return trackers_read(await service.refresh_trackers())
    except ProwlarrError as exc:
        raise prowlarr_unavailable() from exc


@router.put("")
async def save_trackers(
    service: Injected[ReleaseService],
    account: Annotated[Account, Depends(require_session)],
    body: TrackersUpdate,
) -> TrackersRead:
    choices = [
        TrackerChoice(
            indexer_id=c.indexer_id,
            used=c.used,
            auto=c.auto,
            categories=(
                None
                if c.categories is None
                else {
                    "manga": tuple(dict.fromkeys(c.categories.manga)),
                    "ebook": tuple(dict.fromkeys(c.categories.ebook)),
                    "audiobook": tuple(dict.fromkeys(c.categories.audiobook)),
                }
            ),
        )
        for c in body.trackers
    ]
    try:
        return trackers_read(await service.save_trackers(choices, account.username))
    except UnknownCategoryError as exc:
        raise unknown_tracker_category(exc.indexer_ids) from exc
