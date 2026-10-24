"""The connector `deluge`: the JSON-RPC API of the Web UI of Deluge 2 (`POST <url>/json`,
`{"method", "params", "id"}`), signed in with the password of the Web UI (`auth.login`, the
cookie `_session_id`), the Web UI connected to its first daemon when it is not yet.

Every answer is a `200`; a failure is in its `error`: code 1 when the session is not (or no
longer) signed in, code 2 for a method the Web UI does not know (every method of the daemon
until it is connected, `label.*` without the plugin Label), code 4 for an error of the daemon.

The categories of shelfdrop are labels of the plugin Label: without it, shelfdrop does not
send (`check` names it in `TorrentCheck.unsupported`, `add` raises LabelPluginMissingError). A
label is lowercase, of `[a-z0-9_-]` (the categories of shelfdrop are). Deluge has no tags: the
mark of shelfdrop is never set (`mark_placed` does nothing, `TorrentInfo.placed` stays False).

The sessions are kept by HTTP client, address and password (one sign-in for every connector
built on them), signed in again when Deluge forgets one. The address is never logged.
"""

import base64
import posixpath
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Final
from weakref import WeakKeyDictionary

import anyio
import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.client import TorrentConnection
from shelfdrop.clients.torrents.types import TorrentCheck, TorrentInfo, TorrentStatus

# The cookie of a session of the Web UI.
SESSION_COOKIE: Final = "_session_id"
# The codes of `error`: not signed in, a method unknown (the daemon not connected, a plugin off).
NOT_AUTHENTICATED: Final = 1
UNKNOWN_METHOD: Final = 2
# The plugin of the labels, in `core.get_enabled_plugins`.
LABEL_PLUGIN: Final = "Label"
# `TorrentCheck.unsupported` without the plugin Label: a stable token, named by the page.
NO_LABEL_PLUGIN: Final = "label-plugin"
# The fields of `core.get_torrents_status` read for a torrent.
FIELDS: Final = (
    "name",
    "state",
    "progress",
    "download_payload_rate",
    "eta",
    "save_path",
    "label",
    "files",
    "num_seeds",
    "num_peers",
)
# The states of a torrent whose files move (checked, allocated, moved): it waits, even complete.
BUSY: Final = frozenset({"Checking", "Allocating", "Moving"})


class LabelPluginMissingError(ServiceError):
    """The plugin Label of Deluge is off: shelfdrop sends nothing without a label."""


class DelugeSessions:
    """The cookies of the sessions signed in, by address and password, for one HTTP client;
    one sign-in at a time."""

    def __init__(self) -> None:
        self.cookies: dict[tuple[str, str], str] = {}
        self.lock = anyio.Lock()

    async def cookie(
        self, key: tuple[str, str], login: Callable[[], Awaitable[str]], stale: str | None = None
    ) -> str:
        """The cookie of `key`, signed in by `login` when there is none, or only `stale` (the
        one Deluge has just forgotten)."""
        async with self.lock:
            current = self.cookies.get(key)
            if current is not None and current != stale:
                return current
            self.cookies.pop(key, None)
            fresh = await login()
            self.cookies[key] = fresh
            return fresh


# The sessions of each HTTP client of the torrent clients (one in the API, one in the worker).
SESSIONS: Final[WeakKeyDictionary[httpx.AsyncClient, DelugeSessions]] = WeakKeyDictionary()


def sessions_of(http: httpx.AsyncClient) -> DelugeSessions:
    found = SESSIONS.get(http)
    if found is None:
        found = SESSIONS[http] = DelugeSessions()
    return found


def number(value: object, default: float = 0) -> float:
    return (
        float(value) if isinstance(value, int | float) and not isinstance(value, bool) else default
    )


def status_of(state: str, progress: float, speed: int, peers: int) -> TorrentStatus:
    """The generic status of a state of Deluge (`Downloading`, `Seeding`, `Paused`, `Queued`,
    `Checking`, `Allocating`, `Moving`, `Error`). A torrent it has all of is complete, paused or
    queued too, but not while its files move; a torrent that downloads nothing with no peer is
    stalled."""
    if state == "Error":
        return "error"
    if state in BUSY:
        return "waiting"
    if state == "Seeding" or progress >= 1:
        return "complete"
    if state == "Downloading":
        return "stalled" if speed == 0 and peers == 0 else "downloading"
    return "waiting"


def content_path_of(item: dict[str, Any]) -> str:
    """The file of a torrent of one file, the folder of the others (`save_path` and the first
    part of the path of its first file, which keeps a folder renamed in Deluge); `save_path` and
    `name` while a magnet link has no files yet."""
    save_path = item.get("save_path")
    if not isinstance(save_path, str) or not save_path:
        return ""
    files = item.get("files")
    paths = (
        [f["path"] for f in files if isinstance(f, dict) and isinstance(f.get("path"), str)]
        if isinstance(files, list)
        else []
    )
    if len(paths) == 1:
        return posixpath.join(save_path, paths[0])
    if paths:
        return posixpath.join(save_path, paths[0].split("/", 1)[0])
    name = item.get("name")
    return posixpath.join(save_path, name) if isinstance(name, str) and name else ""


def torrent_of(digest: str, item: object) -> TorrentInfo | None:
    """A torrent of `core.get_torrents_status`, or None for an answer without its fields."""
    if not isinstance(item, dict) or "state" not in item:
        return None
    progress = min(1.0, max(0.0, number(item.get("progress")) / 100))
    speed = max(0, int(number(item.get("download_payload_rate"))))
    peers = int(number(item.get("num_seeds"))) + int(number(item.get("num_peers")))
    status = status_of(str(item.get("state")), progress, speed, peers)
    # `eta` is 0 when Deluge cannot tell (no rate) and once complete.
    eta = int(number(item.get("eta")))
    return TorrentInfo(
        hash=digest.lower(),
        name=str(item.get("name") or ""),
        status=status,
        progress=progress,
        speed=speed,
        eta=0 if status == "complete" else (eta if eta > 0 else None),
        category=str(item.get("label") or ""),
        content_path=content_path_of(item),
    )


class DelugeClient:
    """The operations of a torrent client (`shelfdrop.clients.torrents.client.TorrentClient`)
    on the Web UI of Deluge 2."""

    def __init__(self, http: httpx.AsyncClient, url: str | None, password: str | None) -> None:
        self.http = http
        self.url = url
        self.password = password
        self.calls = 0

    @classmethod
    def of(cls, http: httpx.AsyncClient, connection: TorrentConnection) -> "DelugeClient":
        """The address of the Web UI and its password (`torrent.url`, `torrent.password`); the
        Web UI has no user name."""
        return cls(http, connection.url, connection.password)

    def endpoint(self) -> str:
        if not self.url:
            raise ServiceNotConfiguredError("no address")
        if not self.password:
            raise ServiceNotConfiguredError("no password")
        return f"{self.url.rstrip('/')}/json"

    async def post(
        self, method: str, params: Sequence[object], cookie: str | None
    ) -> tuple[dict[str, Any], httpx.Response]:
        """The answer of the Web UI to one call: its body and the response."""
        self.calls += 1
        headers = {"Cookie": f"{SESSION_COOKIE}={cookie}"} if cookie else None
        try:
            response = await self.http.post(
                self.endpoint(),
                json={"method": method, "params": list(params), "id": self.calls},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        if response.status_code != 200:
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        try:
            body = response.json()
        except ValueError as exc:
            raise ServiceError("invalid JSON") from exc
        if not isinstance(body, dict):
            raise ServiceError("unexpected body")
        return body, response

    async def login(self) -> str:
        """`auth.login(password)`: the cookie of the new session. A wrong password answers
        `false`, given as a 401."""
        body, response = await self.post("auth.login", [self.password], None)
        cookie = response.cookies.get(SESSION_COOKIE)
        if body.get("result") is not True or not cookie:
            raise ServiceError("password refused", status=401)
        return cookie

    async def call(self, method: str, *params: object) -> Any:
        """The `result` of `method`, signed in (again when Deluge forgot the session), the Web
        UI connected to its daemon when a method of the daemon is unknown. Raises
        ServiceError for an `error`."""
        self.endpoint()
        sessions = sessions_of(self.http)
        key = (self.url or "", self.password or "")
        cookie = await sessions.cookie(key, self.login)
        body, _ = await self.post(method, params, cookie)
        if code_of(body) == NOT_AUTHENTICATED:
            cookie = await sessions.cookie(key, self.login, stale=cookie)
            body, _ = await self.post(method, params, cookie)
        if code_of(body) == UNKNOWN_METHOD and await self.connect(cookie):
            body, _ = await self.post(method, params, cookie)
        code = code_of(body)
        if code is not None:
            raise ServiceError(f"Deluge error {code}")
        return body.get("result")

    async def connect(self, cookie: str) -> bool:
        """The Web UI connected to its first daemon (`web.get_hosts`, `web.connect`) when it
        is not (`web.connected`): True when it was not."""
        connected, _ = await self.post("web.connected", [], cookie)
        if connected.get("result") is True:
            return False
        hosts, _ = await self.post("web.get_hosts", [], cookie)
        found = hosts.get("result")
        first = found[0] if isinstance(found, list) and found else None
        if not isinstance(first, list) or not first or not isinstance(first[0], str):
            raise ServiceError("no daemon")
        await self.post("web.connect", [first[0]], cookie)
        connected, _ = await self.post("web.connected", [], cookie)
        if connected.get("result") is not True:
            raise ServiceError("daemon unreachable")
        return True

    async def version(self) -> str:
        """`daemon.get_version`: the version of the daemon (`2.2.0`)."""
        version = await self.call("daemon.get_version")
        if not isinstance(version, str) or not version:
            raise ServiceError("unexpected body")
        return version.removeprefix("v")

    async def labelled(self) -> bool:
        """The plugin Label is on (`core.get_enabled_plugins`). `label.*` may still answer
        once it is turned off: the plugins enabled are the ones read."""
        plugins = await self.call("core.get_enabled_plugins")
        return isinstance(plugins, list) and LABEL_PLUGIN in plugins

    async def labels(self) -> list[str]:
        """`label.get_labels`: the labels, lowercase."""
        found = await self.call("label.get_labels")
        if not isinstance(found, list):
            raise ServiceError("unexpected body")
        return [str(label) for label in found]

    async def check(self, categories: Sequence[str]) -> TorrentCheck:
        version = await self.version()
        if not await self.labelled():
            return TorrentCheck(version=version, unsupported=NO_LABEL_PLUGIN)
        found = await self.labels()
        return TorrentCheck(
            version=version, missing=tuple(name for name in categories if name not in found)
        )

    async def add(
        self,
        *,
        category: str,
        file: bytes | None = None,
        magnet: str | None = None,
        directory: str | None = None,
    ) -> None:
        """`core.add_torrent_file` (base64) or `core.add_torrent_magnet`, into `directory`
        when given (`download_location`; otherwise the folder of Deluge), then the label
        `category` (`label.set_torrent`), created first when Deluge lacks it (`label.add`).
        Raises LabelPluginMissingError, before anything is added, without the plugin Label;
        ServiceError when Deluge refuses the torrent (one it already has, a file it cannot
        read)."""
        if file is None and magnet is None:
            raise ServiceError("no torrent")
        if not await self.labelled():
            raise LabelPluginMissingError(NO_LABEL_PLUGIN)
        if category not in await self.labels():
            await self.call("label.add", category)
        options: dict[str, str] = {}
        if directory is not None:
            options["download_location"] = directory
        if file is not None:
            encoded = base64.b64encode(file).decode()
            added = await self.call("core.add_torrent_file", "release.torrent", encoded, options)
        else:
            added = await self.call("core.add_torrent_magnet", magnet, options)
        if not isinstance(added, str) or not added:
            raise ServiceError("torrent refused")
        await self.call("label.set_torrent", added, category)

    async def torrents(self, hashes: Sequence[str]) -> list[TorrentInfo]:
        """`core.get_torrents_status({"id": [...]}, fields)`: the torrents of these hashes it
        has (Deluge knows them in lowercase alone)."""
        if not hashes:
            return []
        found = await self.call(
            "core.get_torrents_status", {"id": [h.lower() for h in hashes]}, list(FIELDS)
        )
        if not isinstance(found, dict):
            raise ServiceError("unexpected body")
        return [t for t in (torrent_of(str(h), item) for h, item in found.items()) if t is not None]

    async def mark_placed(self, hashes: Sequence[str]) -> None:
        """Deluge has no tags: nothing is marked."""


def code_of(body: dict[str, Any]) -> int | None:
    """The code of the `error` of an answer, None without one."""
    error = body.get("error")
    if error is None:
        return None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, int) else -1
