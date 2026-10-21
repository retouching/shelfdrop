"""shelfdrop.works.clients.myanimelist: the official API alone."""

import httpx
import pytest

from shelfdrop.works.clients.myanimelist import MyAnimeListClient
from shelfdrop.works.exceptions import SourceError

ANSWER = {
    "data": [
        {
            "node": {
                "id": 116778,
                "title": "Chainsaw Man",
                "alternative_titles": {
                    "synonyms": ["CSM"],
                    "en": "Chainsaw Man",
                    "ja": "チェンソーマン",
                },
                "num_volumes": 0,
                "authors": [{"node": {"first_name": "Tatsuki", "last_name": "Fujimoto"}}],
                "media_type": "manga",
                "start_date": "2018-12-03",
                "num_list_users": 250000,
                "main_picture": {"medium": "https://cdn.myanimelist.net/images/manga/3/216464.jpg"},
            }
        }
    ]
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_a_search_asks_the_official_api_with_the_client_id() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ANSWER)

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as http:
        [found] = await MyAnimeListClient(http, "client-id-1").search("Chainsaw Man", "manga")

    [request] = seen
    assert request.url.host == "api.myanimelist.net"
    assert request.url.path == "/v2/manga"
    assert request.headers["X-MAL-CLIENT-ID"] == "client-id-1"
    assert "client-id-1" not in str(request.url)
    assert found.source_id == "116778"
    assert found.title == "Chainsaw Man"
    assert found.authors == ("Tatsuki Fujimoto",)
    assert found.year == 2018
    assert found.volumes is None
    assert found.form == "manga"
    assert {(name.title, name.language) for name in found.names} >= {
        ("Chainsaw Man", "en"),
        ("チェンソーマン", "ja"),
    }


@pytest.mark.anyio
async def test_a_refused_client_id_is_a_source_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "invalid_client"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as http:
        with pytest.raises(SourceError):
            await MyAnimeListClient(http, "wrong").search("Berserk", "manga")
