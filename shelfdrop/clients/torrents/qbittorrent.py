"""The connector `qbittorrent`: the WebUI API v2 of qBittorrent itself, signed in with the account
of its WebUI (`POST /api/v2/auth/login`).

The sign-in gives a cookie of session (`SID` in qBittorrent 4.6, `QBT_SID_<port>` in 5.3, F60),
sent with every other request. The factory builds a connector at each use: the cookie is kept
for the next ones in `Sessions`, one store by HTTP client (the container singleton of the torrent
clients), by connection (the address, the account and its password: a password typed for a test
never takes the session of the one saved). A `403` (the session ended, or qBittorrent restarted)
signs in again, once.

The cookie of a sign-in is read from its answer and sent in the header `Cookie` alone: the jar of
the shared HTTP client keeps none. Neither the address, the password nor the cookie is logged.
"""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Final
from weakref import WeakKeyDictionary

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.client import TorrentConnection
from shelfdrop.clients.torrents.webui import REFUSED, WebUiClient

# The path of the sign-in.
LOGIN: Final = "/api/v2/auth/login"


def key_of(url: str, username: str, password: str) -> str:
    """The key of a connection in `Sessions`: a digest, so that no password is a key."""
    return hashlib.sha256("\0".join((url, username, password)).encode()).hexdigest()


@dataclass
class Sessions:
    """The cookies of the sessions of qBittorrent, by connection (`key_of`). One sign-in at a time:
    the requests that need a session wait for the one being opened instead of opening theirs."""

    cookies: dict[str, str] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def cookie(self, key: str, sign_in: Callable[[], Awaitable[str]]) -> str:
        """The cookie of `key`, signed in with `sign_in` when there is none."""
        async with self.lock:
            if key not in self.cookies:
                self.cookies[key] = await sign_in()
            return self.cookies[key]

    def drop(self, key: str, cookie: str) -> None:
        """`cookie` refused: forgotten, unless another request signed in again since."""
        if self.cookies.get(key) == cookie:
            del self.cookies[key]


# The sessions of each HTTP client, gone with it.
SESSIONS: Final[WeakKeyDictionary[httpx.AsyncClient, Sessions]] = WeakKeyDictionary()


def sessions_of(http: httpx.AsyncClient) -> Sessions:
    found = SESSIONS.get(http)
    if found is None:
        found = SESSIONS[http] = Sessions()
    return found


class QbittorrentClient(WebUiClient):
    def __init__(
        self,
        http: httpx.AsyncClient,
        url: str | None,
        username: str | None,
        password: str | None,
    ) -> None:
        super().__init__(http)
        self.url = url
        self.username = username
        self.password = password
        self.sessions = sessions_of(http)

    @classmethod
    def of(cls, http: httpx.AsyncClient, connection: TorrentConnection) -> "QbittorrentClient":
        """The address of the WebUI and its account (`torrent.url`, `torrent.username`,
        `torrent.password`)."""
        return cls(http, connection.url, connection.username, connection.password)

    def base(self) -> str:
        if not self.url:
            raise ServiceNotConfiguredError("no address")
        if not self.username or not self.password:
            raise ServiceNotConfiguredError("no account")
        return self.url.rstrip("/")

    async def sign_in(self) -> str:
        """`POST /api/v2/auth/login` (form): the cookie of a new session, as a `Cookie` header.
        Refused (`refused`): `401` in qBittorrent 5.3, `Fails.` with a `200` in 4.6, `403`
        while the address of shelfdrop is banned after too many failures (F61)."""
        base = self.base()
        try:
            response = await self.http.post(
                f"{base}{LOGIN}",
                data={"username": self.username or "", "password": self.password or ""},
                # The check of qBittorrent against cross-site requests: a Referer, when given,
                # must name the address asked (F62).
                headers={"Referer": f"{base}/"},
            )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        if response.status_code not in (200, 204):
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        if response.text.strip() == REFUSED:
            raise ServiceError("sign-in refused", status=401)
        cookies = dict(response.cookies.items())
        for name in cookies:
            self.http.cookies.delete(name)
        return "; ".join(f"{name}={value}" for name, value in cookies.items())

    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        base = self.base()
        key = key_of(base, self.username or "", self.password or "")
        cookie = await self.sessions.cookie(key, self.sign_in)
        request = {"params": params, "files": files, "data": data}
        response = await self.send(method, base, path, cookie, request)
        if response.status_code == 403:
            # The session ended (its time, a sign-out, a restart of qBittorrent): once again.
            self.sessions.drop(key, cookie)
            cookie = await self.sessions.cookie(key, self.sign_in)
            response = await self.send(method, base, path, cookie, request)
        # 202: qBittorrent took a link it still has to fetch (an answer of its later versions).
        if response.status_code not in (200, 202):
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
        return response

    async def send(
        self, method: str, base: str, path: str, cookie: str, request: dict[str, Any]
    ) -> httpx.Response:
        """One request with the cookie of the session (none: qBittorrent gave none)."""
        headers = {"Referer": f"{base}/"}
        if cookie:
            headers["Cookie"] = cookie
        try:
            return await self.http.request(method, base + path, headers=headers, **request)
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
