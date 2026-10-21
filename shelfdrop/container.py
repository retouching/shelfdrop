"""The one list of wireup registrations, shared by create_app() and the CLI (ADR 0004).

The domain never imports wireup.
"""

from collections.abc import AsyncIterator
from importlib.metadata import version
from typing import Final

import httpx
import wireup
from sqlalchemy import Engine

from shelfdrop.auth.repository import SessionRepository
from shelfdrop.auth.service import AuthService, JellyfinAddress
from shelfdrop.auth.throttle import LoginThrottle
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.qbittorrent import QBittorrentClient
from shelfdrop.config import Settings
from shelfdrop.db.engine import open_engine, open_session
from shelfdrop.releases.clients.prowlarr import ProwlarrClient
from shelfdrop.releases.jobs import SearchBoard
from shelfdrop.releases.repository import ReleaseRepository, repository_factory
from shelfdrop.releases.service import NameLimit, ReleaseService
from shelfdrop.releases.types import ReleaseOptions
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.monitor import ConnectionMonitor
from shelfdrop.settings.probes import ConnectionProbes
from shelfdrop.settings.reader import SettingsReader
from shelfdrop.settings.repository import SettingsRepository, settings_repository_factory
from shelfdrop.settings.service import Probes, SettingsService
from shelfdrop.works.clients.anilist import AniListClient
from shelfdrop.works.clients.bnf import BnfClient
from shelfdrop.works.clients.kitsu import KitsuClient
from shelfdrop.works.clients.mangadex import MangaDexClient
from shelfdrop.works.clients.mangaupdates import MangaUpdatesClient
from shelfdrop.works.clients.myanimelist import MyAnimeListClient
from shelfdrop.works.clients.openlibrary import OpenLibraryClient
from shelfdrop.works.clients.redirect import RedirectTransport
from shelfdrop.works.clients.wikidata import WikidataClient
from shelfdrop.works.flights import SearchFlights, SourceHealth
from shelfdrop.works.repository import WorkRepository
from shelfdrop.works.service import WorkService, WorkSettings, WorkSources
from shelfdrop.works.types import Clock, SearchOptions

# Each request to a source gives up after this; the search gives up on the source after
# SearchOptions.source_timeout_seconds.
REQUEST_TIMEOUT_SECONDS: Final = 4.0
# Each request to Jellyfin, qBittorrent gives up after this.
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


async def open_qbittorrent(settings: Settings) -> AsyncIterator[QBittorrentClient]:
    """The client of qBittorrent (a singleton), on its own HTTP client: its address and its
    key come from the settings at each call."""
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(settings)},
        timeout=httpx.Timeout(SERVICE_TIMEOUT_SECONDS),
    ) as http:
        yield QBittorrentClient(http)


def as_probes(probes: ConnectionProbes) -> Probes:
    return probes


def new_connection_monitor(
    probes: ConnectionProbes, reader: SettingsReader, clock: Clock
) -> ConnectionMonitor:
    """The tests of the services saved, every 5 minutes (a singleton, run by the lifespan)."""
    return ConnectionMonitor(probes, reader, clock)


def as_jellyfin_address(reader: SettingsReader) -> JellyfinAddress:
    return reader


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
        wireup.instance(SearchFlights(), as_type=SearchFlights),
        wireup.instance(SourceHealth(), as_type=SourceHealth),
        wireup.instance(LoginThrottle(), as_type=LoginThrottle),
        wireup.injectable(open_http),
        wireup.injectable(new_secret_box),
        wireup.injectable(new_settings_reader),
        wireup.injectable(as_work_settings),
        wireup.injectable(as_jellyfin_address),
        wireup.injectable(open_jellyfin),
        wireup.injectable(open_qbittorrent),
        wireup.injectable(ConnectionProbes),
        wireup.injectable(as_probes),
        wireup.injectable(new_connection_monitor),
        wireup.injectable(as_name_limit),
        wireup.injectable(new_work_sources),
        wireup.injectable(open_prowlarr),
        wireup.injectable(new_search_board),
        wireup.injectable(open_engine),
        wireup.injectable(open_session, lifetime="scoped"),
        wireup.injectable(WorkRepository, lifetime="scoped"),
        wireup.injectable(WorkService, lifetime="scoped"),
        wireup.injectable(ReleaseRepository, lifetime="scoped"),
        wireup.injectable(ReleaseService, lifetime="scoped"),
        wireup.injectable(SettingsRepository, lifetime="scoped"),
        wireup.injectable(SettingsService, lifetime="scoped"),
        wireup.injectable(SessionRepository, lifetime="scoped"),
        wireup.injectable(AuthService, lifetime="scoped"),
    ]
