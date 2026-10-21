"""qBittorrent (its WebUI API v2), through the client proxy of qui: `<qui>/proxy/<key>` stands
for the address of qBittorrent, and qui signs in to qBittorrent itself.

The key is in the path of every request: an address of qBittorrent is never logged.
"""

from typing import Any

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError


class QBittorrentClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def version(self, url: str | None, api_key: str | None) -> str:
        """`GET /api/v2/app/version`: `v5.1.2`, given without its `v`."""
        response = await self.get(url, api_key, "/api/v2/app/version")
        text = response.text.strip()
        if not text:
            raise ServiceError("unexpected body")
        return text.removeprefix("v")

    async def categories(self, url: str | None, api_key: str | None) -> list[str]:
        """`GET /api/v2/torrents/categories`: the names of the categories."""
        response = await self.get(url, api_key, "/api/v2/torrents/categories")
        try:
            body: Any = response.json()
        except ValueError as exc:
            raise ServiceError("invalid JSON") from exc
        if not isinstance(body, dict):
            raise ServiceError("unexpected body")
        return sorted(str(name) for name in body)

    async def get(self, url: str | None, api_key: str | None, path: str) -> httpx.Response:
        if not url:
            raise ServiceNotConfiguredError("no address")
        if not api_key:
            raise ServiceNotConfiguredError("no key")
        try:
            response = await self.http.get(f"{url.rstrip('/')}/proxy/{api_key}{path}")
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        if response.status_code != 200:
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        return response
