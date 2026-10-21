"""The one list of wireup registrations, shared by create_app() and the CLI (ADR 0004).

The domain never imports wireup.
"""

from collections.abc import AsyncIterator
from importlib.metadata import version
from typing import Final

import httpx
import wireup

from shelfdrop.config import Settings
from shelfdrop.db.engine import open_engine, open_session
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


def new_work_sources(http: httpx.AsyncClient) -> WorkSources:
    """Every metadata client, in the order of the list of the sources that did not answer."""
    return WorkSources(
        clients=(
            MangaUpdatesClient(http),
            KitsuClient(http),
            MyAnimeListClient(http, None),
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
        wireup.instance(SearchFlights(), as_type=SearchFlights),
        wireup.instance(SourceHealth(), as_type=SourceHealth),
        wireup.injectable(open_http),
        wireup.injectable(new_work_sources),
        wireup.injectable(open_engine),
        wireup.injectable(open_session, lifetime="scoped"),
        wireup.injectable(WorkRepository, lifetime="scoped"),
        wireup.injectable(WorkService, lifetime="scoped"),
    ]
