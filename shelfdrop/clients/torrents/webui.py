"""The WebUI API v2 of qBittorrent, shared by the connectors that speak it: `qui` (through the
client proxy of qui) and qBittorrent itself. A connector gives the way to reach the API
(`WebUiClient.call`: its address and how it signs in); the requests, the answers and the states
of qBittorrent are read here alone.

The states of qBittorrent (`stalledDL`, `stoppedUP`...) and its ETA "unknown" (8640000) become
the generic status and ETA of `TorrentInfo` here: no other module reads them.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Final

import httpx

from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.clients.torrents.types import TorrentCheck, TorrentInfo, TorrentStatus

# The body of `POST /api/v2/torrents/add` when qBittorrent 5.0 refused the torrent; later
# versions answer `409` instead.
REFUSED: Final = "Fails."
# The tag of qBittorrent on what shelfdrop placed: a tool that places on its own may leave it alone.
PLACED_TAG: Final = "placé"
# The states of a torrent it has all of (`stoppedUP` from qBittorrent 5, `pausedUP` before).
COMPLETE: Final = frozenset(
    {"uploading", "pausedUP", "stoppedUP", "queuedUP", "stalledUP", "checkingUP", "forcedUP"}
)
# The states of a torrent that downloads; `stalledDL`: it tries to, with no peer.
DOWNLOADING: Final = frozenset({"downloading", "forcedDL"})
STALLED: Final = frozenset({"stalledDL"})
# The states of a torrent stopped on an error. The others (`metaDL`, `queuedDL`, `pausedDL`,
# `stoppedDL`, `checkingDL`, `allocating`, `moving`, `unknown`...) wait.
ERROR: Final = frozenset({"error", "missingFiles"})
# The `eta` of qBittorrent when it cannot tell.
UNKNOWN_ETA: Final = 8640000


def number(value: object, default: float = 0) -> float:
    return (
        float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
    )


def status_of(state: str, progress: float) -> TorrentStatus:
    """The generic status of a state of qBittorrent; a torrent it has all of is complete,
    whatever its state (`moving`, `checkingUP`...)."""
    if progress >= 1 or state in COMPLETE:
        return "complete"
    if state in DOWNLOADING:
        return "downloading"
    if state in STALLED:
        return "stalled"
    if state in ERROR:
        return "error"
    return "waiting"


def eta_of(value: object) -> int | None:
    eta = int(number(value, -1))
    return eta if 0 <= eta < UNKNOWN_ETA else None


def tags_of(value: object) -> frozenset[str]:
    """`tags` of qBittorrent: `a, placé`."""
    text = value if isinstance(value, str) else ""
    return frozenset(tag.strip() for tag in text.split(",") if tag.strip())


def torrent_of(item: object) -> TorrentInfo | None:
    """A torrent of `GET /api/v2/torrents/info`, or None without its hash."""
    if not isinstance(item, dict) or not isinstance(item.get("hash"), str):
        return None
    progress = min(1.0, max(0.0, number(item.get("progress"))))
    return TorrentInfo(
        hash=item["hash"].lower(),
        name=str(item.get("name") or ""),
        status=status_of(str(item.get("state") or "unknown"), progress),
        progress=progress,
        speed=max(0, int(number(item.get("dlspeed")))),
        eta=eta_of(item.get("eta")),
        category=str(item.get("category") or ""),
        content_path=str(item.get("content_path") or ""),
        placed=PLACED_TAG in tags_of(item.get("tags")),
    )


def json_of(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise ServiceError("invalid JSON") from exc


class WebUiClient(ABC):
    """The operations of a torrent client (`shelfdrop.clients.torrents.client.TorrentClient`) on
    the WebUI API v2; a subclass reaches the API (`call`)."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    @abstractmethod
    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        """The answer of the API to `method path` (`/api/v2/app/version`), a `200` or a `202`.
        Raises ServiceNotConfiguredError without an address or a credential, ServiceError
        otherwise (its `status` for an HTTP error, `refused` for 401 and 403)."""

    async def version(self) -> str:
        """`GET /api/v2/app/version`: `v5.1.2`, given without its `v`."""
        response = await self.call("GET", "/api/v2/app/version")
        text = response.text.strip()
        if not text:
            raise ServiceError("unexpected body")
        return text.removeprefix("v")

    async def categories(self) -> list[str]:
        """`GET /api/v2/torrents/categories`: the names of the categories."""
        body = json_of(await self.call("GET", "/api/v2/torrents/categories"))
        if not isinstance(body, dict):
            raise ServiceError("unexpected body")
        return sorted(str(name) for name in body)

    async def check(self, categories: Sequence[str]) -> TorrentCheck:
        version = await self.version()
        found = await self.categories()
        return TorrentCheck(
            version=version, missing=tuple(name for name in categories if name not in found)
        )

    async def torrents(self, hashes: Sequence[str]) -> list[TorrentInfo]:
        """`GET /api/v2/torrents/info?hashes=<a>|<b>`: the torrents of these hashes it has."""
        if not hashes:
            return []
        response = await self.call(
            "GET", "/api/v2/torrents/info", params={"hashes": "|".join(hashes)}
        )
        body = json_of(response)
        if not isinstance(body, list):
            raise ServiceError("unexpected body")
        return [t for t in (torrent_of(item) for item in body) if t is not None]

    async def add(
        self,
        *,
        category: str,
        file: bytes | None = None,
        magnet: str | None = None,
        directory: str | None = None,
    ) -> None:
        """`POST /api/v2/torrents/add` (multipart): a `.torrent` file (`torrents`) or a magnet
        link (`urls`), into `category`, and into `directory` when given (`savepath`; otherwise
        the folder of the category). Raises ServiceError when it refuses it (`Fails.`, `409`,
        `415` for a file it cannot read)."""
        fields: dict[str, Any] = {"category": (None, category)}
        if directory is not None:
            fields["savepath"] = (None, directory)
        if file is not None:
            fields["torrents"] = ("release.torrent", file, "application/x-bittorrent")
        elif magnet is not None:
            fields["urls"] = (None, magnet)
        else:
            raise ServiceError("no torrent")
        response = await self.call("POST", "/api/v2/torrents/add", files=fields)
        if response.text.strip() == REFUSED:
            raise ServiceError("torrent refused")

    async def mark_placed(self, hashes: Sequence[str]) -> None:
        """`POST /api/v2/torrents/addTags` (form): the tag `placé` given to the torrents."""
        if not hashes:
            return
        await self.call(
            "POST",
            "/api/v2/torrents/addTags",
            data={"hashes": "|".join(hashes), "tags": PLACED_TAG},
        )
