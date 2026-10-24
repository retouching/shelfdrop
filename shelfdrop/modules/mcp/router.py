"""The MCP server of shelfdrop (ADR 0022): the tools of plan section 3 quater, on the services of
the page, at `/mcp` (Streamable HTTP, stateless, JSON answers), behind an access token that
`McpMiddleware` checks. Each tool opens a scope of the container of its own: a call runs in the
task group of the MCP server, not in the one of its request."""

from typing import Final

from fastapi import FastAPI
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from shelfdrop.downloads.exceptions import (
    DownloadNotFoundError,
    NotAutomaticError,
    NotRetryableError,
    UnknownReleasesError,
)
from shelfdrop.downloads.service import DownloadService
from shelfdrop.downloads.types import Choice, SendOrder
from shelfdrop.http.dependencies import scope_of
from shelfdrop.http.middleware.mcp import HOLDER_STATE
from shelfdrop.modules.downloads.router import download_read
from shelfdrop.modules.downloads.schemas import DownloadRead, DownloadsRead, ReleaseChoice
from shelfdrop.modules.place.router import item_read, request_of, shelved_read
from shelfdrop.modules.place.schemas import ItemRead, ItemsRead, PlaceBody
from shelfdrop.modules.searches.schemas import ReleaseSearchRead
from shelfdrop.modules.works.schemas import WorkSearchRead
from shelfdrop.ranger.exceptions import ItemBusyError, ItemNotFoundError, RequestRefusedError
from shelfdrop.ranger.service import RangerService
from shelfdrop.releases.exceptions import ProwlarrError, SearchNotFoundError, TooManyNamesError
from shelfdrop.releases.service import ReleaseService
from shelfdrop.releases.types import SearchMode, Volumes
from shelfdrop.tokens.types import StoredToken
from shelfdrop.works.exceptions import NoSourceAnsweredError, QueryTooShortError
from shelfdrop.works.service import WorkService
from shelfdrop.works.types import Kind

INSTRUCTIONS: Final = (
    "shelfdrop finds manga, books and audiobooks, downloads them through qBittorrent and shelves "
    "them in Jellyfin. Find the work first (search_works), then its releases under its names "
    "(search_releases, mode work), and send the ones chosen (grab_releases) with the author, the "
    "series and the volumes; follow them with list_downloads. A text that finds no work goes "
    "to a manual search (mode manual): its downloads wait in Ranger (list_files_to_place, "
    "place_file). Propose the releases to the user before sending any."
)
READ: Final = ToolAnnotations(read_only_hint=True, open_world_hint=True)
WRITE: Final = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)


def token_of(ctx: Context) -> StoredToken:
    """The token McpMiddleware checked for the request of this call."""
    request = ctx.request_context.request
    if request is None:
        raise ToolError("not_signed_in: no request")
    token: StoredToken = request.scope["state"][HOLDER_STATE]
    return token


def require_write(ctx: Context) -> StoredToken:
    token = token_of(ctx)
    if token.scope != "write":
        raise ToolError("token_forbidden: this tool needs a token Lecture et téléchargement")
    return token


def new_mcp_server(app: FastAPI, version: str) -> MCPServer:
    """The MCP server and its tools, on the container of `app`."""
    server = MCPServer(name="shelfdrop", version=version, instructions=INSTRUCTIONS)

    @server.tool(annotations=READ)
    async def search_works(query: str, kind: Kind = "manga") -> WorkSearchRead:
        """Find a work in the metadata sources (MangaUpdates, Kitsu, MyAnimeList, BnF, Open
        Library...): its names in each language, the ones to search, its authors, its volumes
        and its name on the shelf. kind: manga, ebook or audiobook. A title, an ISBN or a link of
        a source."""
        async with scope_of(app) as scope:
            service = await scope.get(WorkService)
            try:
                return WorkSearchRead.model_validate(await service.search(query, kind))
            except QueryTooShortError as exc:
                raise ToolError("query_too_short: 2 letters or digits at least") from exc
            except NoSourceAnsweredError as exc:
                raise ToolError("sources_unavailable: no metadata source answered") from exc

    @server.tool(annotations=READ)
    async def search_releases(
        kind: Kind,
        title: str,
        names: list[str],
        mode: SearchMode = "work",
        refresh: bool = False,
    ) -> ReleaseSearchRead:
        """Search Prowlarr and wait for its releases, ranked and scored as on the page. mode work:
        the names of a work (6 at most, the releases that miss a word of their name set aside;
        those `automatic` may be sent); mode manual: one text, as typed. Each release has its id,
        for grab_releases with the id of the search."""
        async with scope_of(app) as scope:
            service = await scope.get(ReleaseService)
            try:
                progress = await service.start(
                    mode=mode, kind=kind, title=title, names=names, refresh=refresh
                )
                async for _ in service.watch(progress.id):
                    pass
                return ReleaseSearchRead.model_validate(await service.read(progress.id))
            except QueryTooShortError as exc:
                raise ToolError("query_too_short: 2 letters or digits at least") from exc
            except TooManyNamesError as exc:
                raise ToolError("too_many_names: 6 names at most for a work") from exc
            except ProwlarrError as exc:
                raise ToolError("prowlarr_unavailable: Prowlarr does not answer") from exc
            except SearchNotFoundError as exc:
                raise ToolError("search_not_found: the search is no longer kept") from exc

    @server.tool(annotations=WRITE)
    async def grab_releases(
        ctx: Context,
        search_id: str,
        releases: list[ReleaseChoice],
        work_id: str | None = None,
        author: str = "",
        series: str = "",
    ) -> DownloadsRead:
        """Send releases of a search (search_releases) to qBittorrent, each with its volumes;
        a search of a work also needs its work, author and series of the shelf. Sent under the
        name of the token. Only after the user agreed."""
        token = require_write(ctx)
        order = SendOrder(
            search_id=search_id,
            work_id=work_id,
            author=author.strip(),
            series=series.strip(),
            choices=tuple(
                Choice(
                    release_id=r.id,
                    volumes=Volumes(
                        kind=r.volumes.kind, first=r.volumes.first, last=r.volumes.last
                    ),
                )
                for r in releases
            ),
        )
        async with scope_of(app) as scope:
            service = await scope.get(DownloadService)
            try:
                views = await service.send(order, token.name)
            except SearchNotFoundError as exc:
                raise ToolError("search_not_found: the search is no longer kept") from exc
            except UnknownReleasesError as exc:
                raise ToolError(f"release_not_in_search: {', '.join(exc.ids)}") from exc
            except NotAutomaticError as exc:
                raise ToolError(f"release_not_automatic: {', '.join(exc.ids)}") from exc
            return DownloadsRead(downloads=[download_read(v) for v in views])

    @server.tool(annotations=READ)
    async def list_downloads() -> DownloadsRead:
        """The downloads sent, the newest first, with the state, the percent, the speed and the
        time left qBittorrent gives, and where each was shelved."""
        async with scope_of(app) as scope:
            service = await scope.get(DownloadService)
            return DownloadsRead(downloads=[download_read(v) for v in await service.read()])

    @server.tool(annotations=WRITE)
    async def retry_download(ctx: Context, download_id: int) -> DownloadRead:
        """Send again a download qBittorrent did not receive (state failed, reason
        not_received), the same torrent with the same settings."""
        require_write(ctx)
        async with scope_of(app) as scope:
            service = await scope.get(DownloadService)
            try:
                return download_read(await service.retry(download_id))
            except DownloadNotFoundError as exc:
                raise ToolError("download_not_found: no download with this id") from exc
            except NotRetryableError as exc:
                raise ToolError("download_not_retryable: only a torrent not received") from exc

    @server.tool(annotations=READ)
    async def list_files_to_place(query: str = "") -> ItemsRead:
        """The files of Ranger: manual downloads complete, files sent, downloads the placement
        left, files misplaced; with a query, the files of the shelf whose name or path holds it
        too."""
        async with scope_of(app) as scope:
            service = await scope.get(RangerService)
            listing = await service.read(query)
            return ItemsRead(
                items=[item_read(i) for i in listing.items]
                + [shelved_read(s) for s in listing.shelved],
                open=await service.count(),
            )

    @server.tool(annotations=WRITE)
    async def place_file(ctx: Context, item_id: int, request: PlaceBody) -> ItemRead:
        """Link a file of Ranger (the number of its id `item-<n>`) to a work and shelve it: a
        volume, chapters, or the volumes of a release in chapters; or ignore it (`ignore`: left
        where it is, out of the files to place). The placement worker does it within a minute;
        list_files_to_place shows the result."""
        require_write(ctx)
        async with scope_of(app) as scope:
            service = await scope.get(RangerService)
            try:
                return item_read(await service.link(item_id, request_of(request)))
            except ItemNotFoundError as exc:
                raise ToolError("place_item_not_found: no file of Ranger with this id") from exc
            except ItemBusyError as exc:
                raise ToolError("place_item_busy: placed already, or being placed") from exc
            except RequestRefusedError as exc:
                raise ToolError("place_request_refused: the request does not fit") from exc

    return server
