"""shelfdrop.clients.torrents.deluge: the JSON-RPC API of the Web UI of Deluge 2, played by
`FakeDeluge` in the shape Deluge 2.2.0 answers (docs/agents/verified-facts.md, F65 to F69)."""

import base64
import json
import re
import secrets
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.deluge import (
    NO_LABEL_PLUGIN,
    DelugeClient,
    LabelPluginMissingError,
    content_path_of,
    status_of,
)
from shelfdrop.clients.torrents.types import TorrentInfo, TorrentStatus
from shelfdrop.settings.types import TorrentSettings
from shelfdrop.utils.torrent import magnet_id, torrent_id
from tests.unit.clients.support import FakeTorrentSettings, torrent_clients
from tests.unit.support import torrent_file

URL = "http://deluge.test:8112"
PASSWORD = "deluge"
HOST = "88e3b65eda0e466ab1a8deb18fd80136"
LABEL = re.compile(r"[a-z0-9_-]+")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@dataclass
class FakeDeluge:
    """The Web UI of Deluge 2 at `/json`: every answer a `200`, its failure in `error` (code 1:
    not signed in, 2: a method unknown, 4: an error of the daemon). The methods of the daemon
    are unknown until `web.connect`; `label.*` answer even with the plugin off, as Deluge does
    once it is turned off."""

    plugins: list[str] = field(default_factory=lambda: ["Label"])
    labels: list[str] = field(default_factory=list)
    torrents: dict[str, dict[str, Any]] = field(default_factory=dict)
    sessions: set[str] = field(default_factory=set)
    connected: bool = False
    down: bool = False
    calls: list[tuple[str, list[Any]]] = field(default_factory=list)
    added_as: dict[str, Any] = field(
        default_factory=lambda: {
            "state": "Downloading",
            "progress": 0.0,
            "download_payload_rate": 0,
            "eta": 0,
            "num_seeds": 0,
            "num_peers": 0,
        }
    )

    def methods(self) -> list[str]:
        return [method for method, _ in self.calls]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(502, request=request)
        assert request.url.path == "/json"
        body = json.loads(request.content)
        method, params = body["method"], body["params"]
        self.calls.append((method, params))
        if method == "auth.login":
            if params != [PASSWORD]:
                return self.answer(request, body, False)
            session = secrets.token_hex(8)
            self.sessions.add(session)
            response = self.answer(request, body, True)
            response.headers["Set-Cookie"] = f"_session_id={session}; Path=/"
            return response
        if request.headers.get("Cookie", "").removeprefix("_session_id=") not in self.sessions:
            return self.error(request, body, 1, "Not authenticated")
        try:
            return self.answer(request, body, self.call(method, params))
        except LookupError:
            return self.error(request, body, 2, "Unknown method")
        except ValueError as exc:
            return self.error(request, body, 4, f"Failure: {exc}")

    def call(self, method: str, params: list[Any]) -> object:
        if method == "web.connected":
            return self.connected
        if method == "web.get_hosts":
            return [[HOST, "127.0.0.1", 58846, "localclient"]]
        if method == "web.connect":
            assert params == [HOST]
            self.connected = True
            return ["core.add_torrent_file"]
        if not self.connected:
            raise LookupError(method)
        if method.startswith("label.") and not self.labels and "Label" not in self.plugins:
            raise LookupError(method)
        return self.daemon(method, params)

    def daemon(self, method: str, params: list[Any]) -> object:
        match method:
            case "daemon.get_version":
                return "2.2.0"
            case "core.get_enabled_plugins":
                return list(self.plugins)
            case "label.get_labels":
                return list(self.labels)
            case "label.add":
                label = params[0].lower()
                if not LABEL.fullmatch(label):
                    raise ValueError("Invalid label, valid characters:[a-z0-9_-]")
                if label in self.labels:
                    raise ValueError("Label already exists")
                self.labels.append(label)
                return None
            case "label.set_torrent":
                digest, label = params
                if label not in self.labels:
                    raise ValueError("Unknown Label")
                self.torrents[digest]["label"] = label
                return None
            case "core.add_torrent_file":
                return self.add(torrent_id(base64.b64decode(params[1])), params[2])
            case "core.add_torrent_magnet":
                return self.add(magnet_id(params[0]), params[1])
            case "core.get_torrents_status":
                wanted, fields = params[0]["id"], params[1]
                return {
                    digest: {k: v for k, v in torrent.items() if k in fields}
                    for digest, torrent in self.torrents.items()
                    if digest in wanted
                }
        raise LookupError(method)

    def add(self, digest: str | None, options: dict[str, str]) -> str:
        if digest is None:
            raise ValueError("Unable to add torrent, decoding filedump failed")
        if digest in self.torrents:
            raise ValueError(f"Torrent already in session ({digest}).")
        self.torrents[digest] = {
            "name": "Berserk T01.cbz",
            "save_path": options.get("download_location", "/downloads"),
            "files": [{"index": 0, "path": "Berserk T01.cbz", "size": 1024, "offset": 0}],
            "options": options,
            **self.added_as,
        }
        if "Label" in self.plugins:
            self.torrents[digest]["label"] = ""
        return digest

    @staticmethod
    def answer(request: httpx.Request, body: dict[str, Any], result: object) -> httpx.Response:
        return httpx.Response(
            200, json={"result": result, "error": None, "id": body["id"]}, request=request
        )

    @staticmethod
    def error(
        request: httpx.Request, body: dict[str, Any], code: int, message: str
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"result": None, "error": {"message": message, "code": code}, "id": body["id"]},
            request=request,
        )


def new_client(
    deluge: FakeDeluge, url: str | None = URL, password: str | None = PASSWORD
) -> DelugeClient:
    return DelugeClient(httpx.AsyncClient(transport=httpx.MockTransport(deluge)), url, password)


@pytest.mark.anyio
async def test_it_signs_in_connects_its_daemon_and_names_the_labels_it_misses() -> None:
    deluge = FakeDeluge(labels=["manga", "tv"])
    client = new_client(deluge)

    check = await client.check(["manga", "ebook", "audiobook", "shelfdrop-manual"])

    assert check.version == "2.2.0"
    assert check.missing == ("ebook", "audiobook", "shelfdrop-manual")
    assert check.unsupported is None
    assert deluge.methods() == [
        "auth.login",
        "daemon.get_version",
        "web.connected",
        "web.get_hosts",
        "web.connect",
        "web.connected",
        "daemon.get_version",
        "core.get_enabled_plugins",
        "label.get_labels",
    ]


@pytest.mark.anyio
async def test_a_wrong_password_is_refused_and_a_missing_one_asks_nothing() -> None:
    deluge = FakeDeluge()

    with pytest.raises(ServiceError) as refused:
        await new_client(deluge, password="wrong").version()
    with pytest.raises(ServiceNotConfiguredError):
        await new_client(deluge, password=None).version()
    with pytest.raises(ServiceNotConfiguredError):
        await new_client(deluge, url=None).version()

    assert refused.value.refused
    assert deluge.methods() == ["auth.login"]


@pytest.mark.anyio
async def test_one_session_serves_every_connector_and_is_signed_in_again_when_forgotten() -> None:
    deluge = FakeDeluge(connected=True)
    http = httpx.AsyncClient(transport=httpx.MockTransport(deluge))

    await DelugeClient(http, URL, PASSWORD).version()
    await DelugeClient(http, URL, PASSWORD).version()
    deluge.sessions.clear()
    await DelugeClient(http, URL, PASSWORD).version()

    assert deluge.methods() == [
        "auth.login",
        "daemon.get_version",
        "daemon.get_version",
        "daemon.get_version",
        "auth.login",
        "daemon.get_version",
    ]


@pytest.mark.anyio
async def test_without_the_plugin_label_it_is_unsupported_and_sends_nothing() -> None:
    # Turned off after its labels were made: `label.*` still answer.
    deluge = FakeDeluge(plugins=[], labels=["manga"], connected=True)
    client = new_client(deluge)

    check = await client.check(["manga"])
    with pytest.raises(LabelPluginMissingError, match=NO_LABEL_PLUGIN):
        await client.add(category="manga", file=torrent_file("Berserk T01.cbz"))

    assert check.version == "2.2.0"
    assert check.unsupported == "label-plugin"
    assert check.missing == ()
    assert deluge.torrents == {}
    assert "label.get_labels" not in deluge.methods()
    assert isinstance(LabelPluginMissingError("x"), ServiceError)


@pytest.mark.anyio
async def test_a_torrent_is_added_into_its_folder_labelled_and_read_by_its_hash() -> None:
    deluge = FakeDeluge(connected=True)
    client = new_client(deluge)
    data = torrent_file("Berserk T01.cbz")
    digest = torrent_id(data)
    assert digest is not None

    assert await client.torrents([digest]) == []
    await client.add(category="manga", file=data, directory="/data/torrents/manga")
    found = await client.torrents([digest.upper(), "f" * 40])

    assert found == [
        TorrentInfo(
            hash=digest,
            name="Berserk T01.cbz",
            status="stalled",
            progress=0.0,
            speed=0,
            eta=None,
            category="manga",
            content_path="/data/torrents/manga/Berserk T01.cbz",
        )
    ]
    # The label missing is made first, then given.
    assert deluge.labels == ["manga"]
    assert deluge.torrents[digest]["options"] == {"download_location": "/data/torrents/manga"}
    [added] = [params for method, params in deluge.calls if method == "core.add_torrent_file"]
    assert added[0] == "release.torrent"
    assert base64.b64decode(added[1]) == data
    assert deluge.calls[-1] == (
        "core.get_torrents_status",
        [
            {"id": [digest, "f" * 40]},
            [
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
            ],
        ],
    )


@pytest.mark.anyio
async def test_a_magnet_link_goes_into_the_folder_of_deluge_under_a_label_it_has() -> None:
    deluge = FakeDeluge(connected=True, labels=["shelfdrop-manual"])
    client = new_client(deluge)
    magnet = "magnet:?xt=urn:btih:" + "c" * 40

    await client.add(category="shelfdrop-manual", magnet=magnet)

    assert deluge.torrents["c" * 40]["options"] == {}
    assert deluge.torrents["c" * 40]["label"] == "shelfdrop-manual"
    assert "label.add" not in deluge.methods()


@pytest.mark.anyio
async def test_a_torrent_refused_or_a_deluge_down_is_a_service_error() -> None:
    deluge = FakeDeluge(connected=True)
    client = new_client(deluge)
    data = torrent_file("x")
    await client.add(category="manga", file=data)

    with pytest.raises(ServiceError, match="Deluge error 4"):
        await client.add(category="manga", file=data)
    with pytest.raises(ServiceError, match="no torrent"):
        await client.add(category="manga")
    deluge.down = True
    with pytest.raises(ServiceError) as down:
        await client.torrents(["a" * 40])
    assert down.value.status == 502
    # No hash, no request; no mark.
    calls = len(deluge.calls)
    assert await client.torrents([]) == []
    await client.mark_placed(["a" * 40])
    assert len(deluge.calls) == calls


@pytest.mark.anyio
async def test_a_torrent_complete_is_complete_and_never_marked() -> None:
    deluge = FakeDeluge(connected=True)
    deluge.torrents["ab" * 20] = {
        "name": "Berserk T01-T03",
        "state": "Seeding",
        "progress": 100.0,
        "download_payload_rate": 0,
        "eta": 0,
        "label": "manga",
        "save_path": "/data/torrents/manga",
        "files": [
            {"index": 0, "path": "Berserk T01-T03/T01.cbz"},
            {"index": 1, "path": "Berserk T01-T03/sub/T02.cbz"},
        ],
    }
    client = new_client(deluge)

    await client.mark_placed(["ab" * 20])
    [info] = await client.torrents(["ab" * 20])

    assert info.status == "complete"
    assert (info.progress, info.eta, info.placed) == (1.0, 0, False)
    assert info.content_path == "/data/torrents/manga/Berserk T01-T03"


@pytest.mark.parametrize(
    ("state", "progress", "speed", "peers", "expected"),
    [
        ("Seeding", 1.0, 0, 0, "complete"),
        ("Paused", 1.0, 0, 0, "complete"),
        ("Queued", 1.0, 0, 0, "complete"),
        ("Paused", 0.4, 0, 0, "waiting"),
        ("Queued", 0.0, 0, 0, "waiting"),
        ("Checking", 1.0, 0, 0, "waiting"),
        ("Allocating", 0.0, 0, 0, "waiting"),
        ("Moving", 1.0, 0, 0, "waiting"),
        ("Downloading", 0.2, 2048, 3, "downloading"),
        ("Downloading", 0.2, 0, 3, "downloading"),
        ("Downloading", 0.0, 0, 0, "stalled"),
        ("Error", 0.5, 0, 0, "error"),
    ],
)
def test_the_states_of_deluge_become_the_generic_status(
    state: str, progress: float, speed: int, peers: int, expected: TorrentStatus
) -> None:
    assert status_of(state, progress, speed, peers) == expected


def test_the_content_path_is_the_file_of_one_the_folder_of_several() -> None:
    one = {"save_path": "/d", "name": "A.cbz", "files": [{"path": "A.cbz"}]}
    in_folder = {"save_path": "/d", "name": "A", "files": [{"path": "A/A.cbz"}]}
    renamed = {"save_path": "/d/", "name": "A", "files": [{"path": "B/1"}, {"path": "B/2"}]}
    magnet = {"save_path": "/d", "name": "Mag", "files": []}

    assert content_path_of(one) == "/d/A.cbz"
    assert content_path_of(in_folder) == "/d/A/A.cbz"
    assert content_path_of(renamed) == "/d/B"
    assert content_path_of(magnet) == "/d/Mag"
    assert content_path_of({"name": "A"}) == ""


@pytest.mark.anyio
async def test_the_factory_gives_deluge_its_address_and_its_password() -> None:
    deluge = FakeDeluge(connected=True)
    settings = FakeTorrentSettings(
        TorrentSettings(client="deluge", url=URL, username=None, password=PASSWORD, api_key=None)
    )

    client = await torrent_clients(deluge, settings).current()

    assert isinstance(client, DelugeClient)
    assert await client.version() == "2.2.0"
