"""qBittorrent (its WebUI API v2), through the client proxy of qui: `<qui>/proxy/<key>` stands
for the address of qBittorrent, and qui signs in to qBittorrent itself.

The key is in the path of every request: an address of qBittorrent is never logged.
"""

from collections.abc import Sequence
from typing import Any

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.types import TorrentInfo

# The body of `POST /api/v2/torrents/add` when qBittorrent 5.0 refused the torrent; later
# versions answer `409` instead.
REFUSED = "Fails."


def number(value: object, default: float = 0) -> float:
    return (
        float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
    )


def torrent_of(item: object) -> TorrentInfo | None:
    """A torrent of `GET /api/v2/torrents/info`, or None without its hash."""
    if not isinstance(item, dict) or not isinstance(item.get("hash"), str):
        return None
    return TorrentInfo(
        hash=item["hash"].lower(),
        name=str(item.get("name") or ""),
        state=str(item.get("state") or "unknown"),
        progress=min(1.0, max(0.0, number(item.get("progress")))),
        speed=int(number(item.get("dlspeed"))),
        eta=int(number(item.get("eta"))),
        category=str(item.get("category") or ""),
    )


class QBittorrentClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def version(self, url: str | None, api_key: str | None) -> str:
        """`GET /api/v2/app/version`: `v5.1.2`, given without its `v`."""
        response = await self.call("GET", url, api_key, "/api/v2/app/version")
        text = response.text.strip()
        if not text:
            raise ServiceError("unexpected body")
        return text.removeprefix("v")

    async def categories(self, url: str | None, api_key: str | None) -> list[str]:
        """`GET /api/v2/torrents/categories`: the names of the categories."""
        body = json_of(await self.call("GET", url, api_key, "/api/v2/torrents/categories"))
        if not isinstance(body, dict):
            raise ServiceError("unexpected body")
        return sorted(str(name) for name in body)

    async def torrents(
        self, url: str | None, api_key: str | None, hashes: Sequence[str]
    ) -> list[TorrentInfo]:
        """`GET /api/v2/torrents/info?hashes=<a>|<b>`: the torrents of these hashes it has."""
        if not hashes:
            return []
        response = await self.call(
            "GET", url, api_key, "/api/v2/torrents/info", params={"hashes": "|".join(hashes)}
        )
        body = json_of(response)
        if not isinstance(body, list):
            raise ServiceError("unexpected body")
        return [t for t in (torrent_of(item) for item in body) if t is not None]

    async def add(
        self,
        url: str | None,
        api_key: str | None,
        *,
        category: str,
        file: bytes | None = None,
        magnet: str | None = None,
    ) -> None:
        """`POST /api/v2/torrents/add` (multipart): a `.torrent` file (`torrents`) or a magnet
        link (`urls`), into `category`. Raises ServiceError when it refuses it (`Fails.`,
        `409`, `415` for a file it cannot read). The torrent may still be lost after: the
        caller looks for it by its hash."""
        fields: dict[str, Any] = {"category": (None, category)}
        if file is not None:
            fields["torrents"] = ("release.torrent", file, "application/x-bittorrent")
        elif magnet is not None:
            fields["urls"] = (None, magnet)
        else:
            raise ServiceError("no torrent")
        response = await self.call("POST", url, api_key, "/api/v2/torrents/add", files=fields)
        if response.text.strip() == REFUSED:
            raise ServiceError("torrent refused")

    async def call(
        self,
        method: str,
        url: str | None,
        api_key: str | None,
        path: str,
        *,
        params: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
    ) -> httpx.Response:
        if not url:
            raise ServiceNotConfiguredError("no address")
        if not api_key:
            raise ServiceNotConfiguredError("no key")
        try:
            response = await self.http.request(
                method, f"{url.rstrip('/')}/proxy/{api_key}{path}", params=params, files=files
            )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        # 202: qBittorrent took a link it still has to fetch (an answer of its later versions).
        if response.status_code not in (200, 202):
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        return response


def json_of(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise ServiceError("invalid JSON") from exc
