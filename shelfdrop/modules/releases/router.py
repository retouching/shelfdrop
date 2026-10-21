"""The torrent of a release, through Prowlarr: async, since its service holds the async client
of Prowlarr."""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.modules.releases.errors import prowlarr_unavailable, release_not_found
from shelfdrop.releases.exceptions import ProwlarrError, ReleaseNotFoundError
from shelfdrop.releases.service import ReleaseService

router = APIRouter(prefix="/v1/releases", tags=["releases"], route_class=WireupRoute)


@router.get("/{release_id}/torrent", response_model=None)
async def read_torrent(
    service: Injected[ReleaseService], release_id: str
) -> Response | RedirectResponse:
    """The `.torrent` file of a release of a search kept, or a redirect to its magnet link."""
    try:
        torrent = await service.torrent(release_id)
    except ReleaseNotFoundError as exc:
        raise release_not_found() from exc
    except ProwlarrError as exc:
        raise prowlarr_unavailable() from exc
    if torrent.magnet is not None:
        return RedirectResponse(torrent.magnet, status_code=303)
    return Response(torrent.file, media_type="application/x-bittorrent")
