"""shelfdrop.releases.clients.prowlarr: the requests to Prowlarr and the reading of its answers."""

import httpx
import pytest

from shelfdrop.releases.clients.prowlarr import ProwlarrClient
from shelfdrop.releases.exceptions import ProwlarrError, ProwlarrNotConfiguredError
from tests.unit.releases.support import API_KEY, URL, new_prowlarr


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_a_search_sends_the_key_in_a_header_with_its_categories_and_indexers() -> None:
    client, replay = new_prowlarr()

    releases = await client.search("Jujutsu Kaisen", [7030], [1, 2])

    request = replay.requests[0]
    assert request.headers["X-Api-Key"] == API_KEY
    assert "apikey" not in str(request.url)
    assert request.url.params.get_list("categories") == ["7030"]
    assert request.url.params.get_list("indexerIds") == ["1", "2"]
    assert request.url.params["type"] == "search"
    first = releases[0]
    assert first.title == "Jujutsu.Kaisen.T00.FRENCH.MANGA.CBZ.eBook-PapriKa+"
    assert first.indexer == "The Old School"
    assert first.info_hash == f"{101:040x}"
    # The download link of Prowlarr carries its key: it is never kept.
    assert "apikey" not in repr(releases)


@pytest.mark.anyio
async def test_the_indexers() -> None:
    client, _ = new_prowlarr()

    indexers = await client.indexers()

    assert {(i.id, i.name, i.enabled, i.protocol) for i in indexers} >= {
        (5, "YggTorrent", False, "torrent"),
        (6, "NZBgeek", True, "usenet"),
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (httpx.Response(401), "HTTP 401"),
        (httpx.Response(503), "HTTP 503"),
        (httpx.Response(200, content=b"<html>"), "invalid JSON"),
        (httpx.Response(200, json={"message": "?"}), "unexpected body"),
    ],
)
async def test_a_failed_answer_is_a_prowlarr_error(answer: httpx.Response, message: str) -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: answer))
    client = ProwlarrClient(http, URL, API_KEY)

    with pytest.raises(ProwlarrError, match=message):
        await client.search("Berserk", [7030], [1])


@pytest.mark.anyio
async def test_no_answer_is_a_prowlarr_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = ProwlarrClient(httpx.AsyncClient(transport=httpx.MockTransport(refuse)), URL, API_KEY)

    with pytest.raises(ProwlarrError, match="ConnectError"):
        await client.indexers()


@pytest.mark.anyio
async def test_without_address_or_key_nothing_is_asked() -> None:
    client, replay = new_prowlarr()
    client.api_key = ""

    with pytest.raises(ProwlarrNotConfiguredError):
        await client.indexers()
    assert replay.requests == []


@pytest.mark.anyio
async def test_a_release_that_is_not_a_torrent_or_misses_a_field_is_skipped() -> None:
    answer = [
        {"guid": "a", "title": "A", "indexerId": 1, "protocol": "usenet"},
        {"title": "no guid", "indexerId": 1},
        {"guid": "b", "title": "B", "indexerId": 1, "seeders": 3, "protocol": "torrent"},
    ]
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=answer))
    )

    releases = await ProwlarrClient(http, URL, API_KEY).search("x", [7030], [1])

    assert [r.guid for r in releases] == ["b"]
