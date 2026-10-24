"""shelfdrop.settings.probes: the test of each service and source, with the values given."""

from collections.abc import Sequence
from typing import ClassVar

import httpx
import pytest

from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.torrents.client import TorrentConnection
from shelfdrop.clients.torrents.factory import TorrentClients
from shelfdrop.clients.torrents.types import TorrentCheck, TorrentInfo
from shelfdrop.clients.torrents.qui import QuiClient
from shelfdrop.releases.clients.prowlarr import ProwlarrClient, fixed
from shelfdrop.settings.probes import ConnectionProbes
from shelfdrop.works.clients.kitsu import KitsuClient
from shelfdrop.works.clients.myanimelist import MyAnimeListClient
from shelfdrop.works.service import WorkSources
from tests.unit.clients.support import API_KEY as JELLYFIN_KEY
from tests.unit.clients.support import (
    QUI_URL,
    FakeJellyfin,
    FakeQui,
    FakeTorrentSettings,
    torrent_clients,
)
from tests.unit.clients.support import URL as JELLYFIN_URL
from tests.unit.releases.support import API_KEY, URL, ProwlarrReplay
from tests.unit.settings.support import FakeSettingsReader

QUI = QUI_URL


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def http(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]  # the fakes are handlers of MockTransport


class ScriptedClient:
    """A connector of any client: the check it is given, and the connections it was built on."""

    built: ClassVar[list[TorrentConnection]] = []
    answer: ClassVar[TorrentCheck] = TorrentCheck(version="4.0.6")

    @classmethod
    def of(cls, http: httpx.AsyncClient, connection: TorrentConnection) -> "ScriptedClient":
        cls.built.append(connection)
        return cls()

    async def version(self) -> str:
        return self.answer.version

    async def check(self, categories: Sequence[str]) -> TorrentCheck:
        return self.answer

    async def add(
        self,
        *,
        category: str,
        file: bytes | None = None,
        magnet: str | None = None,
        directory: str | None = None,
    ) -> None:
        return None

    async def torrents(self, hashes: Sequence[str]) -> list[TorrentInfo]:
        return []

    async def mark_placed(self, hashes: Sequence[str]) -> None:
        return None


def scripted(answer: TorrentCheck) -> TorrentClients:
    """Every client served by `ScriptedClient`, which answers `answer`, but Deluge."""
    ScriptedClient.built = []
    ScriptedClient.answer = answer
    connectors = {name: ScriptedClient.of for name in ("qui", "qbittorrent", "transmission")}
    return TorrentClients(http(FakeQui()), FakeTorrentSettings(), connectors)


def new_probes(
    sources: httpx.AsyncClient | None = None,
    qui: FakeQui | None = None,
    jellyfin: FakeJellyfin | None = None,
    saved: FakeSettingsReader | None = None,
    torrents: TorrentClients | None = None,
) -> ConnectionProbes:
    source_http = sources or http(lambda r: httpx.Response(200, json={"data": []}))

    async def no_id() -> str | None:
        return None

    return ConnectionProbes(
        ProwlarrClient(http(ProwlarrReplay()), fixed(None, None)),
        torrents or torrent_clients(qui or FakeQui(categories=["manga", "ebook", "audiobook"])),
        JellyfinClient(http(jellyfin or FakeJellyfin()), "0.3.0"),
        WorkSources(clients=(KitsuClient(source_http), MyAnimeListClient(source_http, no_id))),
        saved or FakeSettingsReader(),
    )


@pytest.mark.anyio
async def test_prowlarr_gives_its_version_and_its_indexers_on() -> None:
    result = await new_probes().run("prowlarr", URL, API_KEY)

    assert result.ok
    assert result.version == "2.1.5.5216"
    assert result.count == 4  # on, torrent: C411, Abnormal, Nyaa.si, The Old School


@pytest.mark.anyio
async def test_a_wrong_key_is_refused_with_its_status() -> None:
    result = await new_probes().run("prowlarr", URL, "wrong")

    assert result.state == "refused"
    assert result.status == 401


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("url", "key", "state"), [(None, "k", "no_address"), (URL, None, "no_key")]
)
async def test_without_address_or_key_nothing_is_asked(
    url: str | None, key: str | None, state: str
) -> None:
    assert (await new_probes().run("jellyfin", url, key)).state == state


@pytest.mark.anyio
async def test_the_torrent_client_names_the_categories_of_shelfdrop_it_misses() -> None:
    qui = FakeQui(categories=["manga", "ebook", "audiobook"])

    result = await new_probes(qui=qui).run("torrent", QUI, FakeQui.KEY)

    assert result.service == "torrent"
    assert result.ok
    assert result.version == "5.1.2"
    assert result.count == 3
    assert result.missing == ("shelfdrop-manual",)
    # The client saved (qui by default), at the address typed, with the key typed.
    assert qui.requests[0].url.path == f"/proxy/{FakeQui.KEY}/api/v2/app/version"


@pytest.mark.anyio
async def test_a_torrent_client_no_connector_serves_is_named_so() -> None:
    qui = FakeQui()
    saved = FakeSettingsReader({"torrent.client": "deluge"})

    probes = new_probes(qui=qui, saved=saved)
    # A version of shelfdrop whose connectors serve qui alone.
    probes.torrents.connectors = {"qui": QuiClient.of}

    result = await probes.run("torrent", QUI, "a-password")

    assert (result.state, result.client) == ("no_connector", "deluge")
    assert qui.requests == []


@pytest.mark.anyio
async def test_the_client_typed_is_tested_with_the_username_saved_or_typed() -> None:
    torrents = scripted(TorrentCheck(version="5.1.2"))
    saved = FakeSettingsReader({"torrent.username": "admin"}, {"torrent.api_key": "key"})
    probes = new_probes(saved=saved, torrents=torrents)

    kept = await probes.run("torrent", QUI, "pass", client="qbittorrent")
    typed = await probes.run("torrent", QUI, "pass", client="qbittorrent", username="other")

    assert (kept.state, kept.client, kept.count) == ("connected", "qbittorrent", 4)
    assert typed.ok
    assert [(c.client, c.username, c.password) for c in ScriptedClient.built] == [
        ("qbittorrent", "admin", "pass"),
        ("qbittorrent", "other", "pass"),
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("client", "username", "secret", "state"),
    [
        ("qui", None, None, "no_key"),
        ("qbittorrent", "admin", None, "no_key"),
        ("qbittorrent", "", "pass", "no_key"),
        ("transmission", "admin", None, "no_key"),
        ("transmission", "", "pass", "no_key"),
        ("transmission", "", None, "connected"),
        ("transmission", "admin", "pass", "connected"),
    ],
)
async def test_each_client_needs_its_own_credentials(
    client: str, username: str, secret: str | None, state: str
) -> None:
    probes = new_probes(torrents=scripted(TorrentCheck(version="4.0.6")))

    result = await probes.run("torrent", QUI, secret, client=client, username=username)

    assert result.state == state
    assert len(ScriptedClient.built) == (1 if state == "connected" else 0)


@pytest.mark.anyio
async def test_a_client_shelfdrop_cannot_send_to_is_unsupported_with_its_reason() -> None:
    torrents = scripted(TorrentCheck(version="2.94", unsupported="transmission-version"))

    result = await new_probes(torrents=torrents).run("torrent", QUI, None, client="transmission")

    assert (result.state, result.reason, result.version) == (
        "unsupported",
        "transmission-version",
        "2.94",
    )
    assert not result.ok


@pytest.mark.anyio
async def test_without_address_the_torrent_client_is_not_asked() -> None:
    result = await new_probes(torrents=scripted(TorrentCheck(version="1"))).run(
        "torrent", None, "k"
    )

    assert (result.state, result.client) == ("no_address", "qui")
    assert ScriptedClient.built == []


def test_the_clients_offered_are_those_a_connector_serves() -> None:
    assert new_probes(torrents=scripted(TorrentCheck(version="1"))).clients() == (
        "qui",
        "qbittorrent",
        "transmission",
    )


@pytest.mark.anyio
async def test_jellyfin_gives_its_version_and_its_libraries_of_books() -> None:
    jellyfin = FakeJellyfin(
        libraries=[
            {"Name": "BD & Mangas", "CollectionType": "books"},
            {"Name": "Livres", "CollectionType": "books"},
            {"Name": "Livres audio", "CollectionType": "books"},
            {"Name": "Films", "CollectionType": "movies"},
        ]
    )

    result = await new_probes(jellyfin=jellyfin).run("jellyfin", JELLYFIN_URL, JELLYFIN_KEY)

    assert result.ok
    assert result.version == "10.11.2"
    assert result.count == 3


@pytest.mark.anyio
async def test_unreachable_is_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    probes = new_probes()
    probes.torrents = torrent_clients(refuse, FakeTorrentSettings())

    result = await probes.run("torrent", QUI, FakeQui.KEY)

    assert result.state == "unavailable"
    assert result.status is None


@pytest.mark.anyio
async def test_a_source_answers_a_fixed_search_in_its_time() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    result = await new_probes(sources=http(answer)).run("kitsu", None, None)

    assert result.ok
    assert result.elapsed_ms is not None
    assert "Chainsaw Man" in seen[0].url.params.values()


@pytest.mark.anyio
async def test_myanimelist_is_tested_with_the_client_id_typed() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            403 if request.headers["X-MAL-CLIENT-ID"] == "bad" else 200, json={"data": []}
        )

    probes = new_probes(sources=http(answer))

    without = await probes.run("myanimelist", None, None)
    refused = await probes.run("myanimelist", None, "bad")
    ok = await probes.run("myanimelist", None, "good")

    assert without.state == "no_key"
    assert refused.state == "unavailable"
    assert refused.status == 403
    assert ok.ok
    assert [r.headers["X-MAL-CLIENT-ID"] for r in seen] == ["bad", "good"]
