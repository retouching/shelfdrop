"""shelfdrop.works.clients.redirect."""

import httpx
import pytest

from shelfdrop.works.clients.redirect import RedirectTransport


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_a_request_goes_to_the_origin_with_its_own_in_a_header() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    transport = RedirectTransport("http://fake-sources:8080", httpx.MockTransport(answer))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post(
            "https://api.mangaupdates.com/v1/series/search?x=1", json={"search": "Berserk"}
        )

    assert response.json() == {"ok": True}
    [request] = seen
    assert str(request.url) == "http://fake-sources:8080/v1/series/search?x=1"
    assert request.headers["X-Original-Origin"] == "https://api.mangaupdates.com"
    assert request.headers["Host"] == "fake-sources:8080"
    assert request.content == b'{"search":"Berserk"}'
