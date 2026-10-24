"""shelfdrop.clients.torrents.qbittorrent: the WebUI API v2 of qBittorrent itself, signed in with
the account of its WebUI; its session kept between the connectors built at each use."""

import secrets
from dataclasses import dataclass, field
from typing import Final, Literal

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.qbittorrent import QbittorrentClient
from shelfdrop.clients.torrents.types import TorrentInfo
from shelfdrop.settings.types import TorrentSettings
from shelfdrop.utils.torrent import torrent_id
from tests.unit.clients.support import FakeTorrentSettings, multipart_fields, torrent_clients
from tests.unit.support import torrent_file

URL: Final = "http://qbittorrent.test:8080"
USERNAME: Final = "admin"
PASSWORD: Final = "a-password"
LOGIN: Final = "/api/v2/auth/login"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class FakeQbittorrent:
    """qBittorrent and its WebUI as F60 to F62 observed them: `5.3` signs in with a `204` and the
    cookie `QBT_SID_8080`, refuses with a `401`; `4.6` answers `Ok.` and the cookie `SID`, or
    `Fails.`, with a `200`. A request without a session gets a `403`, as a Referer of another
    address gets a `401`; the address is banned (`403`) after 5 sign-ins refused."""

    version: Literal["5.3", "4.6"] = "5.3"
    sessions: set[str] = field(default_factory=set)
    requests: list[httpx.Request] = field(default_factory=list)
    torrents: dict[str, dict[str, object]] = field(default_factory=dict)
    failures: int = 0

    @property
    def cookie_name(self) -> str:
        return "QBT_SID_8080" if self.version == "5.3" else "SID"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        referer = request.headers.get("Referer")
        if referer is not None and not referer.startswith(URL):
            return httpx.Response(401, text="Unauthorized", request=request)
        if request.url.path == LOGIN:
            return self.login(request)
        if self.session_of(request) not in self.sessions:
            return httpx.Response(403, text="Forbidden", request=request)
        return self.answer(request)

    def session_of(self, request: httpx.Request) -> str | None:
        """The session the header `Cookie` names."""
        for pair in str(request.headers.get("Cookie", "")).split(";"):
            name, _, value = pair.strip().partition("=")
            if name == self.cookie_name:
                return value
        return None

    def login(self, request: httpx.Request) -> httpx.Response:
        if self.failures >= 5:
            return httpx.Response(403, text="Your IP address has been banned", request=request)
        form = dict(httpx.QueryParams(request.read().decode()))
        if (form.get("username"), form.get("password")) != (USERNAME, PASSWORD):
            self.failures += 1
            if self.version == "5.3":
                return httpx.Response(401, text="Unauthorized", request=request)
            return httpx.Response(200, text="Fails.", request=request)
        sid = secrets.token_hex(8)
        self.sessions.add(sid)
        headers = {"Set-Cookie": f"{self.cookie_name}={sid}; HttpOnly; path=/"}
        if self.version == "5.3":
            return httpx.Response(204, headers=headers, request=request)
        return httpx.Response(200, text="Ok.", headers=headers, request=request)

    def answer(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v2/app/version":
            return httpx.Response(200, text=f"v{self.version}.0", request=request)
        if path == "/api/v2/torrents/categories":
            return httpx.Response(200, json={"manga": {"name": "manga"}}, request=request)
        if path == "/api/v2/torrents/add":
            data = multipart_fields(request)
            digest = torrent_id(data["torrents"])
            assert digest is not None
            self.torrents[digest] = {
                "hash": digest,
                "name": "Berserk T01.cbz",
                "state": "stalledDL",
                "progress": 0,
                "dlspeed": 0,
                "eta": 8640000,
                "category": data["category"].decode(),
                "content_path": "/data/torrents/Berserk T01.cbz",
                "tags": "",
            }
            return httpx.Response(200, json={"added_torrent_ids": [digest]}, request=request)
        if path == "/api/v2/torrents/info":
            wanted = str(request.url.params.get("hashes", "")).split("|")
            body = [t for h, t in self.torrents.items() if h in wanted]
            return httpx.Response(200, json=body, request=request)
        if path == "/api/v2/torrents/addTags":
            form = dict(httpx.QueryParams(request.read().decode()))
            for digest in form["hashes"].split("|"):
                self.torrents[digest]["tags"] = form["tags"]
            return httpx.Response(200, request=request)
        return httpx.Response(404, request=request)

    def logins(self) -> int:
        return sum(1 for request in self.requests if request.url.path == LOGIN)


def connection(
    url: str | None = URL, username: str | None = USERNAME, password: str | None = PASSWORD
) -> TorrentSettings:
    return TorrentSettings(
        client="qbittorrent", url=url, username=username, password=password, api_key=None
    )


@pytest.mark.anyio
@pytest.mark.parametrize("version", ["5.3", "4.6"])
async def test_it_signs_in_once_for_the_connectors_built_at_each_use(
    version: Literal["5.3", "4.6"],
) -> None:
    qbittorrent = FakeQbittorrent(version=version)
    torrents = torrent_clients(qbittorrent, FakeTorrentSettings(connection()))

    first = await torrents.current()
    check = await first.check(["manga", "ebook"])
    second = await torrents.current()
    version_again = await second.version()

    assert isinstance(first, QbittorrentClient)
    assert first is not second
    assert check.version == f"{version}.0"
    assert check.missing == ("ebook",)
    assert version_again == f"{version}.0"
    assert qbittorrent.logins() == 1
    login = qbittorrent.requests[0]
    assert login.method == "POST"
    assert dict(httpx.QueryParams(login.read().decode())) == {
        "username": USERNAME,
        "password": PASSWORD,
    }
    assert {r.headers["Referer"] for r in qbittorrent.requests} == {f"{URL}/"}
    # The cookie goes in its header alone: the jar of the shared HTTP client keeps none.
    assert not torrents.http.cookies
    assert all("Cookie" in r.headers for r in qbittorrent.requests[1:])


@pytest.mark.anyio
async def test_a_session_ended_is_opened_again_once() -> None:
    qbittorrent = FakeQbittorrent()
    torrents = torrent_clients(qbittorrent, FakeTorrentSettings(connection()))
    await (await torrents.current()).version()

    qbittorrent.sessions.clear()
    version = await (await torrents.current()).version()

    assert version == "5.3.0"
    assert qbittorrent.logins() == 2
    assert [r.url.path for r in qbittorrent.requests] == [
        LOGIN,
        "/api/v2/app/version",
        "/api/v2/app/version",
        LOGIN,
        "/api/v2/app/version",
    ]
    assert [r.headers.get("Cookie") for r in qbittorrent.requests][2] == (
        qbittorrent.requests[1].headers["Cookie"]
    )


@pytest.mark.anyio
@pytest.mark.parametrize("version", ["5.3", "4.6"])
async def test_a_wrong_password_is_refused_and_keeps_no_session(
    version: Literal["5.3", "4.6"],
) -> None:
    qbittorrent = FakeQbittorrent(version=version)
    torrents = torrent_clients(qbittorrent, FakeTorrentSettings(connection()))
    await (await torrents.current()).version()

    with pytest.raises(ServiceError) as refused:
        await torrents.of(connection(password="wrong")).version()

    assert refused.value.refused
    assert refused.value.status == 401
    # The password typed for a test never takes the session of the one saved.
    assert qbittorrent.logins() == 2
    assert [r.url.path for r in qbittorrent.requests][-1] == LOGIN


@pytest.mark.anyio
async def test_a_banned_address_is_refused_without_a_second_try() -> None:
    qbittorrent = FakeQbittorrent(failures=5)
    client = torrent_clients(qbittorrent, FakeTorrentSettings(connection())).of(connection())

    with pytest.raises(ServiceError) as banned:
        await client.version()

    assert banned.value.status == 403
    assert banned.value.refused
    assert qbittorrent.logins() == 1


@pytest.mark.anyio
async def test_a_session_refused_again_after_a_new_sign_in_is_an_error() -> None:
    qbittorrent = FakeQbittorrent()
    client = torrent_clients(qbittorrent, FakeTorrentSettings(connection())).of(connection())
    await client.version()

    # A session that never works: qBittorrent forgets every one it gives.
    class Forgetful(set[str]):
        def add(self, element: str) -> None:
            pass

    qbittorrent.sessions = Forgetful()

    with pytest.raises(ServiceError) as refused:
        await client.version()

    assert refused.value.status == 403
    assert qbittorrent.logins() == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "missing",
    [{"url": None}, {"username": None}, {"password": None}, {"password": ""}],
)
async def test_an_address_or_an_account_missing_asks_nothing(missing: dict[str, None]) -> None:
    qbittorrent = FakeQbittorrent()
    client = torrent_clients(qbittorrent).of(connection(**missing))

    with pytest.raises(ServiceNotConfiguredError):
        await client.version()

    assert qbittorrent.requests == []


@pytest.mark.anyio
async def test_a_qbittorrent_down_is_a_service_error() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = torrent_clients(down).of(connection())

    with pytest.raises(ServiceError, match="ConnectError"):
        await client.version()


@pytest.mark.anyio
async def test_a_torrent_is_added_listed_and_marked_through_the_session() -> None:
    qbittorrent = FakeQbittorrent()
    client = torrent_clients(qbittorrent).of(connection())
    data = torrent_file("Berserk T01.cbz")
    digest = torrent_id(data)
    assert digest is not None

    await client.add(category="manga", file=data)
    await client.mark_placed([digest])
    found = await client.torrents([digest])

    assert found == [
        TorrentInfo(
            hash=digest,
            name="Berserk T01.cbz",
            status="stalled",
            progress=0.0,
            speed=0,
            eta=None,
            category="manga",
            content_path="/data/torrents/Berserk T01.cbz",
            placed=True,
        )
    ]
    assert qbittorrent.logins() == 1
