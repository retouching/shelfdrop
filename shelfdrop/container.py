"""The one list of wireup registrations, shared by create_app() and the CLI (ADR 0004).

The domain never imports wireup.
"""

from collections.abc import AsyncIterator
from importlib.metadata import version
from typing import Final

import httpx
import wireup
from sqlalchemy import Engine

from shelfdrop.config import Settings
from shelfdrop.db.engine import open_engine, open_session
from shelfdrop.releases.clients.prowlarr import ProwlarrClient
from shelfdrop.releases.jobs import SearchBoard
from shelfdrop.releases.repository import ReleaseRepository, repository_factory
from shelfdrop.releases.service import ReleaseService
from shelfdrop.releases.types import ReleaseOptions
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
from shelfdrop.works.service import WorkService, WorkSources
from shelfdrop.works.types import Clock, SearchOptions

# Each request to a source gives up after this; the search gives up on the source after
# SearchOptions.source_timeout_seconds.
REQUEST_TIMEOUT_SECONDS: Final = 4.0


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


async def open_prowlarr(
    settings: Settings, options: ReleaseOptions
) -> AsyncIterator[ProwlarrClient]:
    """The client of Prowlarr (a singleton), on its own HTTP client: a search of Prowlarr waits
    on every tracker, far longer than a metadata source. Its own deadline comes a little after
    the one of the search (ReleaseOptions.timeout_seconds)."""
    key = settings.prowlarr_api_key
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent(settings)},
        timeout=httpx.Timeout(options.timeout_seconds + 5),
    ) as http:
        yield ProwlarrClient(
            http, settings.prowlarr_url, None if key is None else key.get_secret_value()
        )


def new_search_board(
    prowlarr: ProwlarrClient, engine: Engine, options: ReleaseOptions, clock: Clock
) -> SearchBoard:
    """The searches of Prowlarr of every request (a singleton); its cache on sessions of its
    own, since a search outlives its request."""
    return SearchBoard(prowlarr, repository_factory(engine), options, clock)


def new_work_sources(http: httpx.AsyncClient, settings: Settings) -> WorkSources:
    """Every metadata client, in the order of the list of the sources that did not answer;
    MyAnimeList only with its Client ID."""
    client_id = settings.myanimelist_client_id
    myanimelist = (
        () if client_id is None else (MyAnimeListClient(http, client_id.get_secret_value()),)
    )
    return WorkSources(
        clients=(
            MangaUpdatesClient(http),
            KitsuClient(http),
            *myanimelist,
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
        wireup.injectable(open_http),
        wireup.injectable(new_work_sources),
        wireup.injectable(open_prowlarr),
        wireup.injectable(new_search_board),
        wireup.injectable(open_engine),
        wireup.injectable(open_session, lifetime="scoped"),
        wireup.injectable(WorkRepository, lifetime="scoped"),
        wireup.injectable(WorkService, lifetime="scoped"),
        wireup.injectable(ReleaseRepository, lifetime="scoped"),
        wireup.injectable(ReleaseService, lifetime="scoped"),
    ]
