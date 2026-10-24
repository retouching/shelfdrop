"""shelfdrop.releases.clients.prowlarr: the requests to Prowlarr and the reading of its answers."""

import httpx
import pytest

from shelfdrop.releases.clients.prowlarr import ProwlarrClient, categories_of, fixed, release_of
from shelfdrop.releases.exceptions import ProwlarrError, ProwlarrNotConfiguredError
from shelfdrop.releases.types import Category, Torrent
from tests.unit.releases.support import API_KEY, URL, ProwlarrReplay, new_prowlarr
from tests.unit.support import torrent_file


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
    nyaa = next(i for i in indexers if i.name == "Nyaa.si")
    assert nyaa.categories == (
        Category(id=3000, name="Audio"),
        Category(id=3030, name="Audio/Audiobook"),
        Category(id=7000, name="Books"),
        Category(id=7030, name="Books/Comics"),
        Category(id=100920, name="Literature"),
        Category(id=156719, name="Literature - English-translated"),
    )


def test_the_categories_of_an_indexer_are_flattened_once_each() -> None:
    capabilities = {
        "categories": [
            {
                "id": 7000,
                "name": "Books",
                "subCategories": [
                    {"id": 7030, "name": "Books/Comics", "subCategories": []},
                    {"id": 7035, "name": "Manga"},
                    {"id": "x", "name": "Broken"},
                ],
            },
            {"id": 100920, "name": " Literature ", "subCategories": None},
            {"id": 7030, "name": "Books/Comics"},
            {"name": "No id"},
            "junk",
        ]
    }

    assert categories_of(capabilities) == (
        Category(id=7000, name="Books"),
        Category(id=7030, name="Books/Comics"),
        Category(id=7035, name="Books/Manga"),
        Category(id=100920, name="Literature"),
    )
    assert categories_of(None) == ()


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
    client = ProwlarrClient(http, fixed(URL, API_KEY))

    with pytest.raises(ProwlarrError, match=message):
        await client.search("Berserk", [7030], [1])


@pytest.mark.anyio
async def test_no_answer_is_a_prowlarr_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = ProwlarrClient(
        httpx.AsyncClient(transport=httpx.MockTransport(refuse)), fixed(URL, API_KEY)
    )

    with pytest.raises(ProwlarrError, match="ConnectError"):
        await client.indexers()


@pytest.mark.anyio
async def test_without_address_or_key_nothing_is_asked() -> None:
    replay = ProwlarrReplay()
    client = ProwlarrClient(
        httpx.AsyncClient(transport=httpx.MockTransport(replay)), fixed(URL, None)
    )

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

    releases = await ProwlarrClient(http, fixed(URL, API_KEY)).search("x", [7030], [1])

    assert [r.guid for r in releases] == ["b"]


@pytest.mark.anyio
async def test_the_address_and_the_key_are_read_at_each_call() -> None:
    replay = ProwlarrReplay()
    values = [(URL, "old-key"), (URL, API_KEY)]

    async def connection() -> tuple[str | None, str | None]:
        return values.pop(0)

    client = ProwlarrClient(httpx.AsyncClient(transport=httpx.MockTransport(replay)), connection)

    with pytest.raises(ProwlarrError, match="HTTP 401"):
        await client.indexers()
    assert await client.indexers()


@pytest.mark.anyio
async def test_the_status_gives_the_version() -> None:
    client, _ = new_prowlarr()

    assert await client.version() == "2.1.5.5216"


def test_a_download_link_is_kept_without_its_key() -> None:
    item = {
        "guid": "g",
        "title": "Berserk T01",
        "indexerId": 2,
        "downloadUrl": "http://prowlarr.test/2/download?apikey=secret&link=abc&file=Berserk+T01",
    }
    magnet = {**item, "downloadUrl": None, "magnetUrl": "magnet:?xt=urn:btih:" + "a" * 40}

    kept = release_of(item)
    assert kept is not None
    assert kept.download_url == "http://prowlarr.test/2/download?link=abc&file=Berserk+T01"
    kept = release_of(magnet)
    assert kept is not None
    assert kept.download_url == magnet["magnetUrl"]


@pytest.mark.anyio
async def test_the_torrent_is_asked_at_the_address_of_prowlarr_with_its_key_in_a_header() -> None:
    replay = ProwlarrReplay()
    data = torrent_file("Berserk T01.cbz")
    replay.downloads["abc"] = httpx.Response(200, content=data)
    client, _ = new_prowlarr(replay)

    # A link that names another host is asked at the address of the settings.
    torrent = await client.torrent("http://elsewhere.test/2/download?link=abc&file=Berserk")

    assert torrent == Torrent(file=data)
    request = replay.requests[0]
    assert str(request.url) == f"{URL}/2/download?link=abc&file=Berserk"
    assert request.headers["X-Api-Key"] == API_KEY


@pytest.mark.anyio
async def test_a_magnet_link_is_given_as_it_is_or_as_prowlarr_redirects_to_it() -> None:
    magnet = "magnet:?xt=urn:btih:" + "b" * 40
    replay = ProwlarrReplay()
    replay.downloads["m"] = httpx.Response(301, headers={"Location": magnet})
    client, _ = new_prowlarr(replay)

    assert await client.torrent(magnet) == Torrent(magnet=magnet)
    assert replay.requests == []
    assert await client.torrent(f"{URL}/1/download?link=m") == Torrent(magnet=magnet)


@pytest.mark.anyio
async def test_a_redirect_to_the_tracker_is_followed_without_the_key() -> None:
    data = torrent_file("Berserk T02.cbz")
    asked: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        if request.url.host == "tracker.test":
            return httpx.Response(200, content=data)
        return httpx.Response(302, headers={"Location": "https://tracker.test/dl/7?passkey=p"})

    client = ProwlarrClient(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)), fixed(URL, API_KEY)
    )

    assert await client.torrent(f"{URL}/3/download?link=r") == Torrent(file=data)
    assert "X-Api-Key" not in asked[1].headers


@pytest.mark.anyio
@pytest.mark.parametrize(
    "answer",
    [httpx.Response(410, text="<error/>"), httpx.Response(200, content=b""), httpx.Response(302)],
)
async def test_a_torrent_prowlarr_does_not_give_is_a_prowlarr_error(answer: httpx.Response) -> None:
    replay = ProwlarrReplay()
    replay.downloads["x"] = answer
    client, _ = new_prowlarr(replay)

    with pytest.raises(ProwlarrError):
        await client.torrent(f"{URL}/1/download?link=x")
    with pytest.raises(ProwlarrNotConfiguredError):
        await ProwlarrClient(httpx.AsyncClient(), fixed(URL, None)).torrent(f"{URL}/1/download")
