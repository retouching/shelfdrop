"""The one list of wireup registrations, shared by create_app() and the CLI (ADR 0004).

The domain never imports wireup.
"""

from collections.abc import AsyncIterator, Sequence
from importlib.metadata import version
from typing import Final

import anyio
import anyio.to_thread
import httpx
import wireup
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from shelfdrop.accounts.gate import SetupGate
from shelfdrop.accounts.repository import AccountRepository
from shelfdrop.accounts.service import AccountService, SetupJellyfin
from shelfdrop.auth.repository import SessionRepository
from shelfdrop.auth.service import AuthEvents, AuthService, InternalAccounts, JellyfinAddress
from shelfdrop.auth.throttle import LoginThrottle
from shelfdrop.clients.discord import DiscordClient
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.torrents.factory import ConnectionSource, TorrentClients
from shelfdrop.config import Settings
from shelfdrop.db.engine import open_engine, open_session
from shelfdrop.downloads.covers import DownloadCovers, WorkCoverSource
from shelfdrop.downloads.repository import DownloadRepository, download_repository_factory
from shelfdrop.downloads.sender import DownloadEvents, DownloadSender, TorrentFolders
from shelfdrop.downloads.service import DownloadService, ReleaseFinder
from shelfdrop.downloads.types import DownloadOptions
from shelfdrop.journal.repository import event_repository_factory
from shelfdrop.journal.service import DiscordSettings, Journal, JournalSender
from shelfdrop.journal.types import JournalOptions
from shelfdrop.library.service import LibraryReader, LibraryService, LibrarySettings
from shelfdrop.library.sync import LibrarySync
from shelfdrop.logging.setup import log_file
from shelfdrop.logs.service import LogReader
from shelfdrop.logs.types import LogProcess
from shelfdrop.placement.audio import AudioTools
from shelfdrop.placement.byhand import HandPlacement, HandSettings
from shelfdrop.placement.repository import placement_repository_factory
from shelfdrop.placement.service import (
    CoverSource,
    PlacementEvents,
    PlacementService,
    PlacementSettings,
)
from shelfdrop.placement.types import PlacementOptions
from shelfdrop.placement.worker import PlacementWorker
from shelfdrop.ranger.service import RangerService
from shelfdrop.releases.clients.prowlarr import ProwlarrClient
from shelfdrop.releases.jobs import SearchBoard
from shelfdrop.releases.repository import ReleaseRepository, repository_factory
from shelfdrop.releases.service import NameLimit, ReleaseService
from shelfdrop.releases.types import Release, ReleaseOptions
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.monitor import ConnectionMonitor
from shelfdrop.settings.probes import ConnectionProbes
from shelfdrop.settings.reader import SettingsReader
from shelfdrop.settings.repository import SettingsRepository, settings_repository_factory
from shelfdrop.settings.service import Probes, SettingsService
from shelfdrop.tokens.repository import TokenRepository
from shelfdrop.tokens.service import TokenService
from shelfdrop.tokens.throttle import TokenThrottle
from shelfdrop.uploads.repository import UploadRepository, upload_repository_factory
from shelfdrop.uploads.service import UploadEvents, UploadService
from shelfdrop.uploads.store import UploadStore
from shelfdrop.uploads.types import UploadOptions
from shelfdrop.waiting.repository import waiting_repository_factory
from shelfdrop.waiting.service import (
    LibraryVolumes,
    ReleaseSearcher,
    WaitingEvents,
    WaitingRunner,
    WaitingService,
    WaitingSettings,
)
from shelfdrop.waiting.types import WaitingOptions
from shelfdrop.works.clients.anilist import AniListClient
from shelfdrop.works.clients.bnf import BnfClient
from shelfdrop.works.clients.kitsu import KitsuClient
from shelfdrop.works.clients.mangadex import MangaDexClient
from shelfdrop.works.clients.mangaupdates import MangaUpdatesClient
from shelfdrop.works.clients.myanimelist import MyAnimeListClient
from shelfdrop.works.clients.openlibrary import OpenLibraryClient
from shelfdrop.works.clients.redirect import RedirectTransport
from shelfdrop.works.clients.wikidata import WikidataClient
from shelfdrop.works.covers import WorkCovers
from shelfdrop.works.flights import SearchFlights, SourceHealth
from shelfdrop.works.repository import WorkRepository, work_repository_factory
from shelfdrop.works.service import WorkService, WorkSettings, WorkSources
from shelfdrop.works.types import Clock, Kind, SearchOptions

# Each request to a source gives up after this; the search gives up on the source after
# SearchOptions.source_timeout_seconds.
REQUEST_TIMEOUT_SECONDS: Final = 8.0
# Each request to Jellyfin, the torrent client gives up after this.
SERVICE_TIMEOUT_SECONDS: Final = 10.0


def user_agent(settings: Settings) -> str:
    """The User-Agent the usage policies of the sources ask for: a name, a version, a contact."""
    return f"shelfdrop/{version('shelfdrop')} ({settings.contact})"


async def open_http(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """The HTTP client of the metadata sources (a singleton), closed with the container."""
    transport = (
        None if settings.sources_origin is None else RedirectTransport(settings.sources_origin)
    )
    async with httpx.AsyncClient(
        transport=transport,
        headers={"User-Agent": user_agent(settings)},
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        follow_redirects=True,
    ) as client:
        yield client


def new_secret_box(settings: Settings) -> SecretBox:
    """The key of the secrets (a singleton); the API does not start without it."""
    if settings.secret_key is None:
        msg = "SHELFDROP_SECRET_KEY is not set"
        raise RuntimeError(msg)
    return SecretBox(settings.secret_key.get_secret_value())


def new_settings_reader(engine: Engine, box: SecretBox) -> SettingsReader:
    """The settings read at each call of a service (a singleton), on sessions of its own."""
    return SettingsReader(settings_repository_factory(engine), box)


async def open_jellyfin(settings: Settings) -> AsyncIterator[JellyfinClient]:
    """The client of Jellyfin (a singleton), on its own HTTP client: its address comes from the
    settings at each call, never through the fake origin of the metadata sources."""
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(settings)},
        timeout=httpx.Timeout(SERVICE_TIMEOUT_SECONDS),
    ) as http:
        yield JellyfinClient(http, version("shelfdrop"))


async def open_torrent_clients(
    settings: Settings, reader: SettingsReader
) -> AsyncIterator[TorrentClients]:
    """The connectors of the torrent clients (a singleton), on their own HTTP client: the
    client chosen, its address and its credentials come from the settings at each use."""
    source: ConnectionSource = reader
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(settings)},
        timeout=httpx.Timeout(SERVICE_TIMEOUT_SECONDS),
    ) as http:
        yield TorrentClients(http, source)


async def open_discord(settings: Settings) -> AsyncIterator[DiscordClient]:
    """The client of the webhook of the journal (a singleton): the webhook is read from the
    settings at each message."""
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(settings)},
        timeout=httpx.Timeout(SERVICE_TIMEOUT_SECONDS),
    ) as http:
        yield DiscordClient(http)


def new_journal(engine: Engine, clock: Clock) -> Journal:
    """The events of every process kept as they happen (a singleton), on sessions of their
    own."""
    return Journal(event_repository_factory(engine), clock)


def as_discord_settings(reader: SettingsReader) -> DiscordSettings:
    return reader


def new_journal_sender(
    discord: DiscordClient,
    reader: SettingsReader,
    engine: Engine,
    clock: Clock,
    settings: Settings,
) -> JournalSender:
    """The messages of the journal posted on Discord (a singleton, run by the lifespan of the
    API alone)."""
    return JournalSender(
        discord,
        reader,
        event_repository_factory(engine),
        JournalOptions(batch_seconds=settings.journal_batch_seconds),
        clock,
        settings.public_url,
    )


def as_auth_events(journal: Journal) -> AuthEvents:
    return journal


def as_download_events(journal: Journal) -> DownloadEvents:
    return journal


def new_work_covers(http: httpx.AsyncClient, engine: Engine, clock: Clock) -> WorkCovers:
    """The covers of the works kept from a search, read through the client of the sources."""
    return WorkCovers(work_repository_factory(engine), http, clock)


def as_cover_source(covers: WorkCovers) -> CoverSource:
    return covers


def as_work_cover_source(covers: WorkCovers) -> WorkCoverSource:
    return covers


def new_download_covers(
    source: WorkCoverSource, clock: Clock, settings: Settings
) -> DownloadCovers:
    """The covers of the works of the automatic downloads, for the journal and the page (a
    singleton of each process), taken again by a group after half the batch window."""
    return DownloadCovers(source, clock, settings.journal_batch_seconds)


def as_placement_settings(reader: SettingsReader) -> PlacementSettings:
    return reader


def as_placement_events(journal: Journal) -> PlacementEvents:
    return journal


def new_placement_service(
    engine: Engine,
    torrents: TorrentClients,
    jellyfin: JellyfinClient,
    settings: PlacementSettings,
    covers: CoverSource,
    events: PlacementEvents,
    clock: Clock,
    options: PlacementOptions,
    download_covers: DownloadCovers,
) -> PlacementService:
    """The placement (a singleton of the worker alone): its repositories on sessions of their
    own."""
    return PlacementService(
        placement_repository_factory(engine),
        download_repository_factory(engine),
        torrents,
        jellyfin,
        settings,
        AudioTools(),
        covers,
        events,
        clock,
        options,
        download_covers,
    )


async def run_placement(settings: Settings) -> None:
    """The placement worker, until stopped: the composition root of the process `shelfdrop
    placement run`, on the registrations of the API."""
    container = wireup.create_async_container(injectables=injectables(settings))
    try:
        worker = await container.get(PlacementWorker)
        await worker.run()
    finally:
        await container.close()


def new_log_reader(settings: Settings) -> LogReader:
    """The files of logs of every process, in the data volume they share (ADR 0023)."""
    return LogReader({process: log_file(settings.log_dir, process) for process in LogProcess})


def as_hand_settings(reader: SettingsReader) -> HandSettings:
    return reader


def new_hand_placement(
    placement: PlacementService, settings: HandSettings, store: UploadStore, engine: Engine
) -> HandPlacement:
    """The files of Ranger in the worker, the uploads it takes on sessions of their own."""
    return HandPlacement(placement, settings, upload_repository_factory(engine), store)


def new_upload_store(settings: Settings) -> UploadStore:
    """The chunks and the files sent, in `uploads/` of the data directory: the API writes them,
    the placement worker reads them (the same volume, under another path)."""
    return UploadStore(settings.data_dir / "uploads")


def as_upload_events(journal: Journal) -> UploadEvents:
    return journal


def new_ranger_service(engine: Engine, clock: Clock) -> RangerService:
    return RangerService(placement_repository_factory(engine), clock)


def as_library_settings(reader: SettingsReader) -> LibrarySettings:
    return reader


def new_library_service(
    jellyfin: JellyfinClient,
    settings: LibrarySettings,
    works: WorkService,
    covers: WorkCovers,
    engine: Engine,
    clock: Clock,
) -> LibraryService:
    """The page Jellyfin: the cover.jpg it asks for on sessions of their own."""
    return LibraryService(
        jellyfin, settings, works, covers, placement_repository_factory(engine), clock
    )


class BoardSearcher:
    """The searches of the waiting list: a search of releases of the board, under the names of
    the work, read once it ends, on a session of its own."""

    def __init__(
        self,
        board: SearchBoard,
        prowlarr: ProwlarrClient,
        options: ReleaseOptions,
        clock: Clock,
        reader: SettingsReader,
        engine: Engine,
    ) -> None:
        self.board = board
        self.prowlarr = prowlarr
        self.options = options
        self.clock = clock
        self.reader = reader
        self.engine = engine

    async def releases(self, kind: Kind, title: str, names: Sequence[str]) -> list[Release]:
        session = Session(self.engine, expire_on_commit=False)
        try:
            service = ReleaseService(
                ReleaseRepository(session),
                self.board,
                self.prowlarr,
                self.options,
                self.clock,
                self.reader,
            )
            limit = await self.reader.max_names()
            progress = await service.start(
                mode="work", kind=kind, title=title, names=names[:limit], refresh=True
            )
            async for _ in service.watch(progress.id):
                pass
            return list((await service.read(progress.id)).releases)
        finally:
            await anyio.to_thread.run_sync(session.close)


def as_release_searcher(searcher: BoardSearcher) -> ReleaseSearcher:
    return searcher


def new_library_reader(jellyfin: JellyfinClient, settings: LibrarySettings) -> LibraryReader:
    return LibraryReader(jellyfin, settings)


def new_library_sync(reader: LibraryReader, engine: Engine, clock: Clock) -> LibrarySync:
    """The sync of the metadata to Jellyfin (a singleton: it runs in the background and keeps
    its state), on sessions of its own."""
    return LibrarySync(reader, placement_repository_factory(engine), clock)


def as_library_volumes(reader: LibraryReader) -> LibraryVolumes:
    return reader


def as_waiting_settings(reader: SettingsReader) -> WaitingSettings:
    return reader


def as_waiting_events(journal: Journal) -> WaitingEvents:
    return journal


def new_waiting_service(
    engine: Engine,
    searcher: ReleaseSearcher,
    library: LibraryVolumes,
    settings: WaitingSettings,
    events: WaitingEvents,
    clock: Clock,
) -> WaitingService:
    """The waiting searches (a singleton: its rounds run in the lifespan), on sessions of their
    own."""
    return WaitingService(
        waiting_repository_factory(engine),
        placement_repository_factory(engine),
        searcher,
        library,
        settings,
        events,
        clock,
    )


def as_probes(probes: ConnectionProbes) -> Probes:
    return probes


def new_connection_monitor(
    probes: ConnectionProbes, reader: SettingsReader, clock: Clock
) -> ConnectionMonitor:
    """The tests of the services saved, every 5 minutes (a singleton, run by the lifespan)."""
    return ConnectionMonitor(probes, reader, clock)


def as_jellyfin_address(reader: SettingsReader) -> JellyfinAddress:
    return reader


class SettingsJellyfin:
    """The Jellyfin of the settings as the set-up asks for it: its address saved, and the test
    of the address and the key saved."""

    def __init__(self, reader: SettingsReader, probes: ConnectionProbes) -> None:
        self.reader = reader
        self.probes = probes

    async def jellyfin_url(self) -> str | None:
        return await self.reader.jellyfin_url()

    async def jellyfin_connected(self) -> bool:
        url, key = await self.reader.jellyfin()
        return (await self.probes.run("jellyfin", url, key)).ok


def as_setup_jellyfin(jellyfin: SettingsJellyfin) -> SetupJellyfin:
    return jellyfin


def as_internal_accounts(service: AccountService) -> InternalAccounts:
    return service


def as_work_settings(reader: SettingsReader) -> WorkSettings:
    return reader


def as_name_limit(reader: SettingsReader) -> NameLimit:
    return reader


def environment_values(settings: Settings) -> dict[str, str]:
    """The settings of the environment imported once into the database, by key of the catalog
    of the settings (ADR 0012)."""
    secrets = {
        "prowlarr.api_key": settings.prowlarr_api_key,
        "sources.myanimelist.client_id": settings.myanimelist_client_id,
        "discord.webhook": settings.discord_webhook,
    }
    values = {"prowlarr.url": settings.prowlarr_url, "jellyfin.url": settings.jellyfin_url}
    found = {key: value for key, value in values.items() if value is not None}
    found |= {key: value.get_secret_value() for key, value in secrets.items() if value is not None}
    return found


async def open_prowlarr(
    settings: Settings, options: ReleaseOptions, reader: SettingsReader
) -> AsyncIterator[ProwlarrClient]:
    """The client of Prowlarr (a singleton), on its own HTTP client: a search of Prowlarr waits
    on every tracker, far longer than a metadata source. Its own deadline comes a little after
    the one of the search (ReleaseOptions.timeout_seconds). Its address and its key are read
    from the settings at each call."""
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(settings)},
        timeout=httpx.Timeout(options.timeout_seconds + 5),
    ) as http:
        yield ProwlarrClient(http, reader.prowlarr)


def new_search_board(
    prowlarr: ProwlarrClient,
    engine: Engine,
    options: ReleaseOptions,
    clock: Clock,
    reader: SettingsReader,
) -> SearchBoard:
    """The searches of Prowlarr of every request (a singleton); its cache on sessions of its
    own, since a search outlives its request."""
    return SearchBoard(prowlarr, repository_factory(engine), options, clock, reader)


def as_torrent_folders(reader: SettingsReader) -> TorrentFolders:
    return reader


def as_release_finder(service: ReleaseService) -> ReleaseFinder:
    return service


def new_download_sender(
    prowlarr: ProwlarrClient,
    torrents: TorrentClients,
    reader: SettingsReader,
    engine: Engine,
    options: DownloadOptions,
    clock: Clock,
    journal: Journal,
    covers: DownloadCovers,
) -> DownloadSender:
    """The sends to the torrent client of every request (a singleton, resumed by the lifespan);
    its downloads on sessions of their own, since a send outlives its request."""
    return DownloadSender(
        prowlarr,
        torrents,
        reader,
        download_repository_factory(engine),
        options,
        clock,
        journal,
        covers,
    )


def new_work_sources(http: httpx.AsyncClient, reader: SettingsReader) -> WorkSources:
    """Every metadata client, in the order of the list of the sources that did not answer;
    MyAnimeList reads its Client ID at each search, and is asked only with it."""
    return WorkSources(
        clients=(
            MangaUpdatesClient(http),
            KitsuClient(http),
            MyAnimeListClient(http, reader.myanimelist_client_id),
            AniListClient(http),
            MangaDexClient(http),
            BnfClient(http),
            OpenLibraryClient(http),
            WikidataClient(http),
        )
    )


def injectables(settings: Settings) -> list[object]:
    """Values and singletons, then the scoped session, repositories and services."""
    return [
        wireup.instance(settings, as_type=Settings),
        wireup.instance(
            SearchOptions(source_rest_seconds=settings.source_rest_seconds), as_type=SearchOptions
        ),
        wireup.instance(Clock(), as_type=Clock),
        wireup.instance(ReleaseOptions(), as_type=ReleaseOptions),
        wireup.instance(
            DownloadOptions(check_seconds=settings.send_check_seconds), as_type=DownloadOptions
        ),
        wireup.instance(
            PlacementOptions(every_seconds=settings.placement_every_seconds),
            as_type=PlacementOptions,
        ),
        wireup.instance(
            WaitingOptions(every_seconds=settings.waiting_every_seconds), as_type=WaitingOptions
        ),
        wireup.instance(UploadOptions(), as_type=UploadOptions),
        wireup.instance(SearchFlights(), as_type=SearchFlights),
        wireup.instance(SourceHealth(), as_type=SourceHealth),
        wireup.instance(LoginThrottle(), as_type=LoginThrottle),
        wireup.instance(SetupGate(), as_type=SetupGate),
        wireup.instance(TokenThrottle(), as_type=TokenThrottle),
        wireup.injectable(open_http),
        wireup.injectable(new_secret_box),
        wireup.injectable(new_settings_reader),
        wireup.injectable(as_work_settings),
        wireup.injectable(as_jellyfin_address),
        wireup.injectable(open_jellyfin),
        wireup.injectable(open_torrent_clients),
        wireup.injectable(ConnectionProbes),
        wireup.injectable(as_probes),
        wireup.injectable(SettingsJellyfin),
        wireup.injectable(as_setup_jellyfin),
        wireup.injectable(new_connection_monitor),
        wireup.injectable(as_name_limit),
        wireup.injectable(new_work_sources),
        wireup.injectable(open_prowlarr),
        wireup.injectable(new_search_board),
        wireup.injectable(as_torrent_folders),
        wireup.injectable(new_download_sender),
        wireup.injectable(open_discord),
        wireup.injectable(new_journal),
        wireup.injectable(as_discord_settings),
        wireup.injectable(new_journal_sender),
        wireup.injectable(as_auth_events),
        wireup.injectable(as_download_events),
        wireup.injectable(new_work_covers),
        wireup.injectable(as_cover_source),
        wireup.injectable(as_work_cover_source),
        wireup.injectable(new_download_covers),
        wireup.injectable(as_placement_settings),
        wireup.injectable(as_placement_events),
        wireup.injectable(new_placement_service),
        wireup.injectable(as_hand_settings),
        wireup.injectable(new_upload_store),
        wireup.injectable(as_upload_events),
        wireup.injectable(new_hand_placement),
        wireup.injectable(PlacementWorker),
        wireup.injectable(new_ranger_service),
        wireup.injectable(as_library_settings),
        wireup.injectable(BoardSearcher),
        wireup.injectable(as_release_searcher),
        wireup.injectable(new_library_reader),
        wireup.injectable(new_library_sync),
        wireup.injectable(as_library_volumes),
        wireup.injectable(as_waiting_settings),
        wireup.injectable(as_waiting_events),
        wireup.injectable(new_waiting_service),
        wireup.injectable(WaitingRunner),
        wireup.injectable(new_log_reader),
        wireup.injectable(new_library_service, lifetime="scoped"),
        wireup.injectable(open_engine),
        wireup.injectable(open_session, lifetime="scoped"),
        wireup.injectable(WorkRepository, lifetime="scoped"),
        wireup.injectable(WorkService, lifetime="scoped"),
        wireup.injectable(ReleaseRepository, lifetime="scoped"),
        wireup.injectable(ReleaseService, lifetime="scoped"),
        wireup.injectable(as_release_finder, lifetime="scoped"),
        wireup.injectable(DownloadRepository, lifetime="scoped"),
        wireup.injectable(DownloadService, lifetime="scoped"),
        wireup.injectable(SettingsRepository, lifetime="scoped"),
        wireup.injectable(SettingsService, lifetime="scoped"),
        wireup.injectable(AccountRepository, lifetime="scoped"),
        wireup.injectable(AccountService, lifetime="scoped"),
        wireup.injectable(as_internal_accounts, lifetime="scoped"),
        wireup.injectable(SessionRepository, lifetime="scoped"),
        wireup.injectable(AuthService, lifetime="scoped"),
        wireup.injectable(TokenRepository, lifetime="scoped"),
        wireup.injectable(TokenService, lifetime="scoped"),
        wireup.injectable(UploadRepository, lifetime="scoped"),
        wireup.injectable(UploadService, lifetime="scoped"),
    ]
