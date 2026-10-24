"""The connector `transmission`: the RPC of Transmission (`POST <url>/transmission/rpc`), in its
classic protocol (`{"method", "arguments"}`, kebab-case and camelCase names), which Transmission
3.00 speaks and 4.x still serves next to its JSON-RPC 2.0.

- The address: the one of Transmission (`http://transmission:9091`), its RPC path added; an
  address that already ends with `/rpc` is taken as it is (an RPC behind another path), one of
  its web interface (`.../transmission/web/`) gives the RPC next to it.
- The session id: Transmission answers `409` with `X-Transmission-Session-Id` to a request
  without the id of its session; the id is kept by address, for the next connectors, and the
  request sent again once.
- Its credentials: HTTP basic, `torrent.username` and `torrent.password`, both optional (a
  Transmission may ask for none).
- Its labels play the categories: a torrent is added with the label of its category (and into
  the folder of its kind, `download-dir`); the mark of shelfdrop is one more label, `placé`.
  Transmission has no list of labels: a label exists once a torrent carries it, so none is ever
  missing. The labels came with Transmission 3.00 (RPC version 16; `torrent-add` takes them from
  4.0.0, RPC version 17, they are set after the add before): an older Transmission is refused.

No address, header or body is logged: the address may carry credentials.
"""

import asyncio
import base64
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, ClassVar, Final

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.client import TorrentConnection
from shelfdrop.clients.torrents.types import TorrentCheck, TorrentInfo, TorrentStatus

SESSION_HEADER: Final = "X-Transmission-Session-Id"
RPC_PATH: Final = "/transmission/rpc"
# The label of Transmission on what shelfdrop placed (the tag `placé` of qBittorrent).
PLACED_LABEL: Final = "placé"
# The RPC version of Transmission 3.00, the first with labels, and of 4.0.0, the first whose
# `torrent-add` takes them.
LABELS_RPC: Final = 16
ADD_LABELS_RPC: Final = 17
# Why shelfdrop cannot send to a Transmission older than 3.00 (`TorrentCheck.unsupported`).
TOO_OLD: Final = "transmission-version"
# `status` of `torrent-get`: 0 stopped, 1 queued to verify, 2 verifying, 3 queued to download,
# 4 downloading, 5 queued to seed, 6 seeding.
DOWNLOADING: Final = 4
# `error` of `torrent-get`: 1 and 2 a warning or an error of a tracker (the torrent goes on),
# 3 an error of its files (it stops).
LOCAL_ERROR: Final = 3
FIELDS: Final = (
    "hashString",
    "name",
    "status",
    "percentDone",
    "rateDownload",
    "eta",
    "downloadDir",
    "labels",
    "error",
    "peersSendingToUs",
    "files",
)


class TransmissionTooOldError(ServiceError):
    """A Transmission older than 3.00: no labels, shelfdrop does not send to it."""


def rpc_url(url: str) -> str:
    """The address of the RPC of the Transmission at `url`."""
    base = url.rstrip("/")
    if base.endswith("/rpc"):
        return base
    if base.endswith("/transmission/web"):
        return base.removesuffix("/web") + "/rpc"
    if base.endswith("/transmission"):
        return base + "/rpc"
    return base + RPC_PATH


def number(value: object, default: float = 0) -> float:
    return (
        float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
    )


def labels_of(value: object) -> list[str]:
    return [str(label) for label in value] if isinstance(value, list) else []


def status_of(item: dict[str, Any], progress: float) -> TorrentStatus:
    """The generic status of a torrent of `torrent-get`."""
    if number(item.get("error")) == LOCAL_ERROR:
        return "error"
    if progress >= 1:
        return "complete"
    if number(item.get("status")) == DOWNLOADING:
        return "downloading" if number(item.get("peersSendingToUs")) > 0 else "stalled"
    return "waiting"


def content_path_of(item: dict[str, Any]) -> str:
    """The file of a torrent of one file, the root folder of the others: `downloadDir` and the
    first part of the name of its first file (the files of Transmission are named from that
    folder: `Folder/a.mp3`); "" for a magnet link without its files yet."""
    files = item.get("files")
    folder = item.get("downloadDir")
    if not isinstance(files, list) or not files or not isinstance(folder, str) or not folder:
        return ""
    first = files[0].get("name") if isinstance(files[0], dict) else None
    if not isinstance(first, str) or not first:
        return ""
    return str(PurePosixPath(folder) / PurePosixPath(first).parts[0])


def torrent_of(item: object) -> TorrentInfo | None:
    """A torrent of `torrent-get`, or None without its hash."""
    if not isinstance(item, dict) or not isinstance(item.get("hashString"), str):
        return None
    progress = min(1.0, max(0.0, number(item.get("percentDone"))))
    labels = labels_of(item.get("labels"))
    eta = int(number(item.get("eta"), -1))
    return TorrentInfo(
        hash=item["hashString"].lower(),
        name=str(item.get("name") or ""),
        status=status_of(item, progress),
        progress=progress,
        speed=max(0, int(number(item.get("rateDownload")))),
        # -1: not available, -2: unknown.
        eta=eta if eta >= 0 else None,
        category=next((label for label in labels if label != PLACED_LABEL), ""),
        content_path=content_path_of(item),
        placed=PLACED_LABEL in labels,
    )


@dataclass(frozen=True)
class Session:
    """What `session-get` says of Transmission."""

    version: str
    rpc_version: int


class SessionIds:
    """The session ids of Transmission by address of its RPC, shared by the connectors (built
    again at each use); a new id is taken under the lock of its loop, once for the requests that
    met the same `409`."""

    def __init__(self) -> None:
        self.ids: dict[str, str] = {}
        self.locks: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Lock]] = {}

    def lock(self, url: str) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        held = self.locks.get(url)
        if held is None or held[0] is not loop:
            held = (loop, asyncio.Lock())
            self.locks[url] = held
        return held[1]


class TransmissionClient:
    sessions: ClassVar[SessionIds] = SessionIds()

    def __init__(
        self,
        http: httpx.AsyncClient,
        url: str | None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.http = http
        self.url = url
        self.auth = (
            httpx.BasicAuth(username or "", password or "") if username or password else None
        )

    @classmethod
    def of(cls, http: httpx.AsyncClient, connection: TorrentConnection) -> "TransmissionClient":
        """The address of Transmission and its credentials, if it asks for some
        (`torrent.url`, `torrent.username`, `torrent.password`)."""
        return cls(http, connection.url, connection.username, connection.password)

    async def post(self, url: str, body: dict[str, Any], session: str) -> httpx.Response:
        try:
            return await self.http.post(
                url,
                json=body,
                headers={SESSION_HEADER: session},
                auth=self.auth or httpx.USE_CLIENT_DEFAULT,
            )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc

    async def call(self, method: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """The `arguments` of the answer of Transmission to `method`. Raises
        ServiceNotConfiguredError without an address, ServiceError when it does not answer,
        refuses (`refused` for 401 and 403) or answers another `result` than `success`."""
        if not self.url:
            raise ServiceNotConfiguredError("no address")
        url = rpc_url(self.url)
        body: dict[str, Any] = {"method": method, "arguments": arguments or {}}
        used = self.sessions.ids.get(url, "")
        response = await self.post(url, body, used)
        if response.status_code == 409:
            async with self.sessions.lock(url):
                if self.sessions.ids.get(url, "") == used:
                    self.sessions.ids[url] = response.headers.get(SESSION_HEADER, "")
                used = self.sessions.ids[url]
            response = await self.post(url, body, used)
        if response.status_code != 200:
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        try:
            answer = response.json()
        except ValueError as exc:
            raise ServiceError("invalid JSON") from exc
        if not isinstance(answer, dict) or not isinstance(answer.get("arguments", {}), dict):
            raise ServiceError("unexpected body")
        # `result`: `success`, or what went wrong (`unrecognized info` for a file it cannot
        # read), never logged.
        if answer.get("result") != "success":
            raise ServiceError(f"{method} refused")
        arguments_of: dict[str, Any] = answer.get("arguments", {})
        return arguments_of

    async def session(self) -> Session:
        """`session-get`: `4.1.3 (838877323f)` and its RPC version."""
        found = await self.call("session-get", {"fields": ["version", "rpc-version"]})
        version = found.get("version")
        rpc_version = found.get("rpc-version")
        if not isinstance(version, str) or not version.strip() or not isinstance(rpc_version, int):
            raise ServiceError("unexpected body")
        return Session(version=version.split()[0], rpc_version=rpc_version)

    async def version(self) -> str:
        return (await self.session()).version

    async def check(self, categories: Sequence[str]) -> TorrentCheck:
        """The labels play the categories and exist once a torrent carries them: none is
        missing; a Transmission older than 3.00 has none, it is `unsupported`."""
        session = await self.session()
        if session.rpc_version < LABELS_RPC:
            return TorrentCheck(version=session.version, unsupported=TOO_OLD)
        return TorrentCheck(version=session.version)

    async def add(
        self,
        *,
        category: str,
        file: bytes | None = None,
        magnet: str | None = None,
        directory: str | None = None,
    ) -> None:
        """`torrent-add`: a `.torrent` file (`metainfo`, in base64) or a magnet link
        (`filename`), with the label `category`, into `directory` when given (`download-dir`;
        otherwise the folder of Transmission). A torrent it already has (`torrent-duplicate`)
        is taken as added. Raises TransmissionTooOldError before 3.00, ServiceError when it
        refuses the torrent (`torrent-add refused`)."""
        if file is not None:
            arguments: dict[str, Any] = {"metainfo": base64.b64encode(file).decode()}
        elif magnet is not None:
            arguments = {"filename": magnet}
        else:
            raise ServiceError("no torrent")
        session = await self.session()
        if session.rpc_version < LABELS_RPC:
            raise TransmissionTooOldError(f"Transmission {session.version} is older than 3.00")
        arguments["labels"] = [category]
        if directory is not None:
            arguments["download-dir"] = directory
        added = await self.call("torrent-add", arguments)
        torrent = added.get("torrent-added")
        if session.rpc_version < ADD_LABELS_RPC and isinstance(torrent, dict):
            # Transmission 3.00 leaves the labels of `torrent-add` aside.
            digest = torrent.get("hashString")
            if isinstance(digest, str):
                await self.call("torrent-set", {"ids": [digest], "labels": [category]})

    async def listed(self, hashes: Sequence[str], fields: Sequence[str]) -> list[Any]:
        found = await self.call("torrent-get", {"ids": list(hashes), "fields": list(fields)})
        torrents = found.get("torrents")
        if not isinstance(torrents, list):
            raise ServiceError("unexpected body")
        return torrents

    async def torrents(self, hashes: Sequence[str]) -> list[TorrentInfo]:
        """`torrent-get` on the ids `hashes`: the torrents of these hashes it has."""
        wanted = [digest for digest in hashes if digest]
        if not wanted:
            return []
        items = await self.listed(wanted, FIELDS)
        return [t for t in (torrent_of(item) for item in items) if t is not None]

    async def mark_placed(self, hashes: Sequence[str]) -> None:
        """The label `placé` added to the labels of each torrent (`torrent-set` replaces the
        list: it is read first)."""
        wanted = [digest for digest in hashes if digest]
        if not wanted:
            return
        for item in await self.listed(wanted, ("hashString", "labels")):
            if not isinstance(item, dict) or not isinstance(item.get("hashString"), str):
                continue
            labels = labels_of(item.get("labels"))
            if PLACED_LABEL not in labels:
                await self.call(
                    "torrent-set",
                    {"ids": [item["hashString"]], "labels": [*labels, PLACED_LABEL]},
                )
