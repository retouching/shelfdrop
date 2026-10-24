"""shelfdrop.clients.torrents.transmission: the RPC of Transmission, its session id, its optional
credentials, its labels as the categories and the mark of shelfdrop."""

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Final

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.torrents.transmission import (
    TOO_OLD,
    SessionIds,
    TransmissionClient,
    TransmissionTooOldError,
    rpc_url,
    torrent_of,
)
from shelfdrop.clients.torrents.types import TorrentInfo
from shelfdrop.settings.types import TorrentSettings
from shelfdrop.utils.torrent import magnet_id, torrent_id
from tests.unit.clients.support import FakeTorrentSettings, torrent_clients
from tests.unit.support import torrent_file

URL: Final = "http://transmission.test:9091"
USER: Final = "admin"
PASSWORD: Final = "transmission-password-of-the-tests"
RPC: Final = f"{URL}/transmission/rpc"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def fresh_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """The session ids kept by address start empty in each test."""
    monkeypatch.setattr(TransmissionClient, "sessions", SessionIds())


@dataclass
class FakeTransmission:
    """The RPC of Transmission as its daemon 4.1.3 answers it (F70-F74): basic credentials
    checked first (`401`), then the session id (`409` with `X-Transmission-Session-Id`), then
    `{"result", "arguments"}`. `rpc_version` 16 is Transmission 3.00: `torrent-add` leaves its
    labels aside; 15 and before have none."""

    credentials: tuple[str, str] | None = (USER, PASSWORD)
    session_id: str = "session-1"
    version: str = "4.1.3 (838877323f)"
    rpc_version: int = 19
    torrents: dict[str, dict[str, Any]] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    added_as: dict[str, Any] = field(
        default_factory=lambda: {"status": 4, "percentDone": 0.0, "peersSendingToUs": 0}
    )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path != "/transmission/rpc":
            return httpx.Response(404, request=request)
        if self.credentials is not None:
            user, password = self.credentials
            expected = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
            if request.headers.get("Authorization") != expected:
                return httpx.Response(401, request=request)
        if request.headers.get("X-Transmission-Session-Id") != self.session_id:
            headers = {"X-Transmission-Session-Id": self.session_id}
            return httpx.Response(409, headers=headers, request=request)
        body = json.loads(request.content)
        result, arguments = self.answer(body["method"], body.get("arguments", {}))
        return httpx.Response(200, json={"result": result, "arguments": arguments})

    def answer(self, method: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if method == "session-get":
            return "success", {"version": self.version, "rpc-version": self.rpc_version}
        if method == "torrent-add":
            return self.add(arguments)
        if method == "torrent-get":
            wanted = [str(i).lower() for i in arguments["ids"]]
            found = [
                {k: v for k, v in t.items() if k in arguments["fields"]}
                for h, t in self.torrents.items()
                if h in wanted
            ]
            return "success", {"torrents": found}
        if method == "torrent-set":
            labels = arguments["labels"]
            if any("," in label for label in labels):
                return "labels cannot contain comma (,) character", {}
            for digest in arguments["ids"]:
                if digest in self.torrents and self.rpc_version >= 16:
                    self.torrents[digest]["labels"] = list(labels)
            return "success", {}
        return "no method name", {}

    def add(self, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if "metainfo" in arguments:
            digest = torrent_id(base64.b64decode(arguments["metainfo"]))
        else:
            digest = magnet_id(arguments.get("filename", ""))
        if digest is None:
            return "unrecognized info", {}
        if digest in self.torrents:
            named = {"hashString": digest, "id": 1, "name": self.torrents[digest]["name"]}
            return "success", {"torrent-duplicate": named}
        self.torrents[digest] = {
            "hashString": digest,
            "name": f"Torrent {digest[:6]}",
            "downloadDir": arguments.get("download-dir", "/downloads/complete"),
            "labels": list(arguments.get("labels", [])) if self.rpc_version >= 17 else [],
            "rateDownload": 0,
            "eta": -2,
            "error": 0,
            "files": [],
            **self.added_as,
        }
        named = {"hashString": digest, "id": 1, "name": self.torrents[digest]["name"]}
        return "success", {"torrent-added": named}

    def calls(self) -> list[str]:
        """The methods of the requests that went through (neither a 401 nor a 409)."""
        return [
            json.loads(r.content)["method"]
            for r in self.requests
            if r.headers.get("X-Transmission-Session-Id") == self.session_id
        ]

    def bodies(self, method: str) -> list[dict[str, Any]]:
        found = [json.loads(r.content) for r in self.requests]
        return [b["arguments"] for b in found if b["method"] == method]


def new_client(
    fake: FakeTransmission,
    url: str | None = URL,
    username: str | None = USER,
    password: str | None = PASSWORD,
) -> TransmissionClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    return TransmissionClient(http, url, username, password)


def test_the_address_of_transmission_gives_its_rpc() -> None:
    assert rpc_url("http://t:9091") == "http://t:9091/transmission/rpc"
    assert rpc_url("http://t:9091/") == "http://t:9091/transmission/rpc"
    assert rpc_url("http://t:9091/transmission") == "http://t:9091/transmission/rpc"
    assert rpc_url("http://t:9091/transmission/web/") == "http://t:9091/transmission/rpc"
    assert rpc_url("https://t.example/torrents/rpc") == "https://t.example/torrents/rpc"
    assert rpc_url("http://t:9091/transmission/rpc/") == "http://t:9091/transmission/rpc"


@pytest.mark.anyio
async def test_the_session_id_is_taken_from_the_409_and_kept_for_the_next_connectors() -> None:
    fake = FakeTransmission()

    check = await new_client(fake).check(["manga", "ebook", "audiobook", "shelfdrop-manual"])
    # Another connector on the same address (the factory builds one at each use).
    version = await new_client(fake).version()

    assert check.version == "4.1.3"
    assert check.missing == ()
    assert check.unsupported is None
    assert version == "4.1.3"
    assert [r.url for r in fake.requests] == [httpx.URL(RPC)] * 3
    assert fake.requests[0].headers["X-Transmission-Session-Id"] == ""
    assert [r.headers["X-Transmission-Session-Id"] for r in fake.requests[1:]] == [
        "session-1",
        "session-1",
    ]
    assert fake.bodies("session-get")[0] == {"fields": ["version", "rpc-version"]}


@pytest.mark.anyio
async def test_a_session_id_expired_is_taken_again_once() -> None:
    fake = FakeTransmission()
    client = new_client(fake)
    await client.version()
    fake.session_id = "session-2"

    assert await client.version() == "4.1.3"
    assert len(fake.requests) == 4

    class Rotating(FakeTransmission):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            # A new id at every request: the second 409 is an error.
            self.session_id = f"session-{len(self.requests) + 1}"
            return super().__call__(request)

    with pytest.raises(ServiceError) as again:
        await new_client(Rotating(), url="http://other.test:9091").version()
    assert again.value.status == 409


@pytest.mark.anyio
async def test_the_credentials_are_optional_and_wrong_ones_are_refused() -> None:
    open_fake = FakeTransmission(credentials=None)
    await new_client(open_fake, username=None, password=None).version()
    assert all("Authorization" not in r.headers for r in open_fake.requests)

    fake = FakeTransmission()
    with pytest.raises(ServiceError) as refused:
        await new_client(fake, password="wrong").version()
    assert refused.value.refused
    assert len(fake.requests) == 1

    with pytest.raises(ServiceNotConfiguredError):
        await new_client(fake, url=None).version()
    assert len(fake.requests) == 1


@pytest.mark.anyio
async def test_a_transmission_older_than_3_00_is_unsupported_and_never_sent_to() -> None:
    fake = FakeTransmission(version="2.94 (d8e60ee44f)", rpc_version=15)
    client = new_client(fake)

    check = await client.check(["manga"])
    with pytest.raises(TransmissionTooOldError, match=r"older than 3\.00"):
        await client.add(category="manga", file=torrent_file("Berserk T01.cbz"))

    assert check.version == "2.94"
    assert check.unsupported == TOO_OLD == "transmission-version"
    assert "torrent-add" not in fake.calls()


@pytest.mark.anyio
async def test_a_torrent_is_added_with_its_label_into_its_folder_and_read_by_its_hash() -> None:
    fake = FakeTransmission(added_as={"status": 4, "percentDone": 0.42, "peersSendingToUs": 3})
    client = new_client(fake)
    data = torrent_file("Berserk T01.cbz")
    digest = torrent_id(data)
    assert digest is not None
    fake.torrents["f" * 40] = {"hashString": "f" * 40, "name": "Other", "labels": ["tv"]}

    assert await client.torrents([digest]) == []
    await client.add(category="manga", file=data, directory="/data/torrents/manga")
    found = await client.torrents([digest, "a" * 40])

    assert fake.bodies("torrent-add") == [
        {
            "metainfo": base64.b64encode(data).decode(),
            "labels": ["manga"],
            "download-dir": "/data/torrents/manga",
        }
    ]
    assert found == [
        TorrentInfo(
            hash=digest,
            name=f"Torrent {digest[:6]}",
            status="downloading",
            progress=0.42,
            speed=0,
            eta=None,
            category="manga",
        )
    ]
    assert fake.bodies("torrent-get")[-1]["ids"] == [digest, "a" * 40]
    # No hash, no request.
    requests = len(fake.requests)
    assert await client.torrents([]) == []
    assert await client.torrents([""]) == []
    await client.mark_placed([""])
    assert len(fake.requests) == requests


@pytest.mark.anyio
async def test_a_magnet_link_without_a_folder_goes_where_transmission_puts_it() -> None:
    fake = FakeTransmission()
    magnet = "magnet:?xt=urn:btih:" + "c" * 40

    await new_client(fake).add(category="shelfdrop-manual", magnet=magnet)

    assert fake.bodies("torrent-add") == [{"filename": magnet, "labels": ["shelfdrop-manual"]}]
    assert fake.torrents["c" * 40]["downloadDir"] == "/downloads/complete"


@pytest.mark.anyio
async def test_transmission_3_00_gets_the_label_after_the_add() -> None:
    fake = FakeTransmission(version="3.00 (bb6b5a062e)", rpc_version=16)
    data = torrent_file("Berserk T02.cbz")
    digest = torrent_id(data)

    await new_client(fake).add(category="manga", file=data)

    assert fake.calls() == ["session-get", "torrent-add", "torrent-set"]
    assert fake.bodies("torrent-set") == [{"ids": [digest], "labels": ["manga"]}]
    assert fake.torrents[str(digest)]["labels"] == ["manga"]


@pytest.mark.anyio
async def test_a_torrent_refused_is_an_error_and_a_duplicate_is_taken() -> None:
    fake = FakeTransmission()
    client = new_client(fake)
    data = torrent_file("Berserk T03.cbz")

    with pytest.raises(ServiceError, match="torrent-add refused"):
        await client.add(category="manga", file=b"not a torrent")
    with pytest.raises(ServiceError, match="no torrent"):
        await client.add(category="manga")
    await client.add(category="manga", file=data)
    await client.add(category="manga", file=data)

    assert len(fake.torrents) == 1


@pytest.mark.parametrize(
    ("fields", "status"),
    [
        ({"status": 4, "percentDone": 0.5, "peersSendingToUs": 2}, "downloading"),
        ({"status": 4, "percentDone": 0.5, "peersSendingToUs": 0}, "stalled"),
        ({"status": 6, "percentDone": 1.0}, "complete"),
        ({"status": 0, "percentDone": 1.0}, "complete"),
        ({"status": 5, "percentDone": 1.0}, "complete"),
        ({"status": 0, "percentDone": 0.3}, "waiting"),
        ({"status": 1, "percentDone": 0.0}, "waiting"),
        ({"status": 2, "percentDone": 0.6}, "waiting"),
        ({"status": 3, "percentDone": 0.0}, "waiting"),
        # A tracker that warns or fails: the torrent goes on.
        ({"status": 4, "percentDone": 0.5, "peersSendingToUs": 1, "error": 2}, "downloading"),
        # Its files: it stops.
        ({"status": 0, "percentDone": 1.0, "error": 3}, "error"),
    ],
)
def test_the_status_of_transmission_becomes_the_generic_one(
    fields: dict[str, Any], status: str
) -> None:
    info = torrent_of({"hashString": "AB" * 20, **fields})

    assert info is not None
    assert info.status == status
    assert info.hash == "ab" * 20


def test_the_eta_unknown_or_not_available_is_none() -> None:
    def eta(value: int) -> int | None:
        info = torrent_of({"hashString": "a" * 40, "eta": value})
        assert info is not None
        return info.eta

    assert (eta(96), eta(0), eta(-1), eta(-2)) == (96, 0, None, None)
    assert torrent_of({"name": "no hash"}) is None


def test_the_content_path_is_the_file_of_one_file_or_the_root_folder() -> None:
    single = torrent_of(
        {
            "hashString": "a" * 40,
            "name": "Berserk T01.cbz",
            "downloadDir": "/data/torrents/manga/",
            "files": [{"name": "Berserk T01.cbz", "length": 10, "bytesCompleted": 10}],
        }
    )
    several = torrent_of(
        {
            "hashString": "b" * 40,
            "name": "Dune",
            "downloadDir": "/data/torrents/audio",
            "files": [{"name": "Dune/01.mp3"}, {"name": "Dune/cd2/02.mp3"}],
        }
    )
    magnet = torrent_of({"hashString": "c" * 40, "downloadDir": "/data/x", "files": []})

    assert single is not None
    assert several is not None
    assert magnet is not None
    assert single.content_path == "/data/torrents/manga/Berserk T01.cbz"
    assert several.content_path == "/data/torrents/audio/Dune"
    assert magnet.content_path == ""


@pytest.mark.anyio
async def test_the_mark_of_shelfdrop_is_one_more_label_the_others_kept() -> None:
    fake = FakeTransmission()
    fake.torrents["ab" * 20] = {
        "hashString": "ab" * 20,
        "name": "Berserk T01.cbz",
        "status": 6,
        "percentDone": 1.0,
        "labels": ["manga", "seed-forever"],
    }
    client = new_client(fake)

    [info] = await client.torrents(["ab" * 20])
    await client.mark_placed(["ab" * 20])
    [marked] = await client.torrents(["ab" * 20])
    await client.mark_placed(["ab" * 20])

    assert (info.category, info.placed) == ("manga", False)
    assert (marked.category, marked.placed, marked.status) == ("manga", True, "complete")
    assert fake.torrents["ab" * 20]["labels"] == ["manga", "seed-forever", "placé"]
    # Marked once: the second time reads it and sets nothing.
    assert fake.bodies("torrent-set") == [
        {"ids": ["ab" * 20], "labels": ["manga", "seed-forever", "placé"]}
    ]


@pytest.mark.anyio
async def test_the_factory_builds_it_from_the_settings_of_transmission() -> None:
    fake = FakeTransmission(credentials=None)
    settings = FakeTorrentSettings(
        TorrentSettings(client="transmission", url=URL, username=None, password=None, api_key=None)
    )

    client = await torrent_clients(fake, settings).current()

    assert isinstance(client, TransmissionClient)
    assert (await client.check(["manga"])).version == "4.1.3"
