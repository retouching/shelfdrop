"""Prowlarr (its API v1): the search of releases, the list of its indexers, its status, and the
torrent of a release.

Its address and its key are read at each call (`Connection`): the settings page may change them
at any time. The key goes in the header `X-Api-Key`, never in the address. A download link of
Prowlarr (`downloadUrl`, `magnetUrl`: `<prowlarr>/<indexer>/download?apikey=...&link=...`) is
kept without its `apikey`, and asked at the address of Prowlarr of the settings alone, the key
in the header: the key never goes to another host, nor into the database.
"""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Final
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from shelfdrop.releases.exceptions import ProwlarrError, ProwlarrNotConfiguredError
from shelfdrop.releases.types import FoundRelease, Indexer, Torrent

# Releases asked for each name: more than a page shows, fewer than a slow tracker sends.
LIMIT = 100
# A torrent file larger than this is refused: no real one comes near.
MAX_TORRENT_BYTES: Final = 10 * 1024 * 1024
REDIRECTS: Final = frozenset({301, 302, 303, 307, 308})

# The address and the API key of Prowlarr, None when unset.
type Connection = Callable[[], Awaitable[tuple[str | None, str | None]]]


def fixed(url: str | None, api_key: str | None) -> Connection:
    """A connection that does not change: the values typed before they are saved."""

    async def connection() -> tuple[str | None, str | None]:
        return url, api_key

    return connection


class ProwlarrClient:
    def __init__(self, http: httpx.AsyncClient, connection: Connection) -> None:
        self.http = http
        self.connection = connection

    async def search(
        self, query: str, categories: Sequence[int], indexer_ids: Sequence[int]
    ) -> list[FoundRelease]:
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("query", query),
            ("type", "search"),
            ("limit", LIMIT),
        ]
        params += [("categories", c) for c in categories]
        params += [("indexerIds", i) for i in indexer_ids]
        body = await self.get("/api/v1/search", params)
        if not isinstance(body, list):
            raise ProwlarrError("unexpected body")
        return [r for r in (release_of(item) for item in body) if r is not None]

    async def indexers(self) -> list[Indexer]:
        body = await self.get("/api/v1/indexer", [])
        if not isinstance(body, list):
            raise ProwlarrError("unexpected body")
        return [
            Indexer(
                id=int(item["id"]),
                name=str(item.get("name") or item["id"]),
                enabled=bool(item.get("enable")),
                language=item.get("language") or None,
                protocol=str(item.get("protocol") or ""),
            )
            for item in body
            if isinstance(item, dict) and "id" in item
        ]

    async def version(self) -> str:
        """The version of Prowlarr (`GET /api/v1/system/status`)."""
        body = await self.get("/api/v1/system/status", [])
        if not isinstance(body, dict) or not isinstance(body.get("version"), str):
            raise ProwlarrError("unexpected body")
        return str(body["version"])

    async def torrent(self, link: str) -> Torrent:
        """The torrent behind a download link of a release (`FoundRelease.download_url`):
        `GET /<indexer>/download` gives the `.torrent` file, or redirects to a magnet link, or,
        for an indexer set to redirect, to the link of the tracker, asked without the key."""
        if link.startswith("magnet:"):
            return Torrent(magnet=link)
        url, api_key = await self.connection()
        if not url or not api_key:
            raise ProwlarrNotConfiguredError("not configured")
        base, parts = urlsplit(url), urlsplit(link)
        target = urlunsplit((base.scheme, base.netloc, parts.path, parts.query, ""))
        try:
            response = await self.http.get(
                target, headers={"X-Api-Key": api_key}, follow_redirects=False
            )
            location = response.headers.get("Location", "")
            if response.status_code in REDIRECTS and location.startswith("magnet:"):
                return Torrent(magnet=location)
            if response.status_code in REDIRECTS and location.startswith(("http://", "https://")):
                response = await self.http.get(location, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise ProwlarrError(type(exc).__name__) from exc
        if response.status_code != 200:
            raise ProwlarrError(f"HTTP {response.status_code}", status=response.status_code)
        if not response.content or len(response.content) > MAX_TORRENT_BYTES:
            raise ProwlarrError("unexpected body")
        return Torrent(file=response.content)

    async def get(
        self, path: str, params: list[tuple[str, str | int | float | bool | None]]
    ) -> Any:
        url, api_key = await self.connection()
        if not url or not api_key:
            raise ProwlarrNotConfiguredError("not configured")
        try:
            response = await self.http.get(
                f"{url.rstrip('/')}{path}", params=params, headers={"X-Api-Key": api_key}
            )
        except httpx.HTTPError as exc:
            raise ProwlarrError(type(exc).__name__) from exc
        if response.status_code != 200:
            raise ProwlarrError(f"HTTP {response.status_code}", status=response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise ProwlarrError("invalid JSON") from exc


def without_key(link: object) -> str | None:
    """A download link of Prowlarr without its `apikey`; a magnet link as it is."""
    if not isinstance(link, str) or not link:
        return None
    if link.startswith("magnet:"):
        return link
    parts = urlsplit(link)
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() != "apikey"
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def release_of(item: object) -> FoundRelease | None:
    """A release of `GET /api/v1/search`, or None when it is not a torrent or misses a field."""
    if not isinstance(item, dict) or item.get("protocol") not in (None, "torrent"):
        return None
    try:
        return FoundRelease(
            guid=str(item["guid"]),
            title=str(item["title"]),
            indexer_id=int(item["indexerId"]),
            indexer=str(item.get("indexer") or ""),
            size=int(item.get("size") or 0),
            seeders=int(item.get("seeders") or 0),
            info_url=item.get("infoUrl") or None,
            info_hash=(str(item["infoHash"]).lower() if item.get("infoHash") else None),
            publish_date=item.get("publishDate") or None,
            download_url=without_key(item.get("downloadUrl") or item.get("magnetUrl")),
        )
    except (KeyError, TypeError, ValueError):
        return None
