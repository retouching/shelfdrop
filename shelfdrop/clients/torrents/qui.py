"""The connector `qui`: the WebUI API v2 of qBittorrent through the client proxy of qui.
`<qui>/proxy/<key>` stands for the address of qBittorrent, and qui signs in to qBittorrent itself.

The key is in the path of every request: an address of qBittorrent is never logged.
"""

from typing import Any

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.client import TorrentConnection
from shelfdrop.clients.torrents.webui import WebUiClient


class QuiClient(WebUiClient):
    def __init__(self, http: httpx.AsyncClient, url: str | None, api_key: str | None) -> None:
        super().__init__(http)
        self.url = url
        self.api_key = api_key

    @classmethod
    def of(cls, http: httpx.AsyncClient, connection: TorrentConnection) -> "QuiClient":
        """The address of qui and the key of its client proxy (`torrent.url`,
        `torrent.api_key`)."""
        return cls(http, connection.url, connection.api_key)

    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        if not self.url:
            raise ServiceNotConfiguredError("no address")
        if not self.api_key:
            raise ServiceNotConfiguredError("no key")
        try:
            response = await self.http.request(
                method,
                f"{self.url.rstrip('/')}/proxy/{self.api_key}{path}",
                params=params,
                files=files,
                data=data,
            )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        # 202: qBittorrent took a link it still has to fetch (an answer of its later versions).
        if response.status_code not in (200, 202):
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        return response
