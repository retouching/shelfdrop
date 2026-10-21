"""The sources of the work search through the real API: the ones that fail, the cache of their
answers, and one run for two identical searches."""

import concurrent.futures
from typing import Any

import httpx
import pytest

from tests.integration.support import ORIGINAL_ORIGIN, FakeSources, Stack

pytestmark = [pytest.mark.works, pytest.mark.works_sources]

MANGAUPDATES = "https://api.mangaupdates.com"
SEARCH_PATH = "/v1/series/search"


def test_the_sources_that_fail_are_named(client: httpx.Client) -> None:
    """AniList refused when the fixtures were recorded; MyAnimeList, without a Client ID in the
    test stack, is not asked."""
    body = client.get("/api/v1/works", params={"q": "Chainsaw Man", "kind": "manga"}).json()

    assert body["unavailable"] == ["anilist"]
    assert body["works"]


def test_no_source_answering_is_a_503(client: httpx.Client) -> None:
    """A search no source was recorded with: every source answers 404."""
    response = client.get("/api/v1/works", params={"q": "zzz never recorded qq", "kind": "manga"})

    assert response.status_code == 503
    assert response.json() == {
        "code": "sources_unavailable",
        "detail": "No metadata source answered",
        "data": None,
    }


def test_a_book_search_asks_the_book_sources_alone(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    before = fake_sources.count(MANGAUPDATES, SEARCH_PATH, body_contains="Can't Hurt Me")

    body = client.get("/api/v1/works", params={"q": "Can't Hurt Me", "kind": "ebook"}).json()

    assert body["works"][0]["shelf_name"] == "Plus rien ne pourra me blesser"
    assert set(body["works"][0]["sources"]) <= {"openlibrary", "wikidata", "bnf"}
    assert fake_sources.count(MANGAUPDATES, SEARCH_PATH, body_contains="Can't Hurt Me") == before


def test_a_second_search_reads_the_answers_kept(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    params = {"q": "Kaguya-sama", "kind": "manga"}
    first = client.get("/api/v1/works", params=params).json()
    asked = fake_sources.count(MANGAUPDATES, SEARCH_PATH, body_contains="Kaguya-sama")

    second = client.get("/api/v1/works", params={"q": " kaguya-SAMA ", "kind": "manga"}).json()

    assert asked >= 1
    assert fake_sources.count(MANGAUPDATES, SEARCH_PATH, body_contains="Kaguya-sama") == asked
    assert second["works"] == first["works"]


def test_two_identical_searches_at_once_share_one_run(
    stack: Stack, fake_sources: FakeSources, signed_in: dict[str, str]
) -> None:
    """A text of this test alone, whose MangaUpdates answer takes a second: the second request
    comes while the first one runs, and waits for its answer."""
    text = "shared flight 4b1e"
    fake_sources.load([slow_empty_search(text)])

    def search(_: int) -> httpx.Response:
        return httpx.get(
            f"{stack.base_url}/api/v1/works",
            params={"q": text, "kind": "manga"},
            headers=signed_in,
            timeout=30.0,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(search, range(2))

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert fake_sources.count(MANGAUPDATES, SEARCH_PATH, body_contains=text) == 1


def slow_empty_search(text: str) -> dict[str, Any]:
    """MangaUpdates finds nothing for `text`, after a second."""
    return {
        "request": {
            "method": "POST",
            "urlPath": SEARCH_PATH,
            "headers": {ORIGINAL_ORIGIN: {"equalTo": MANGAUPDATES}},
            "bodyPatterns": [{"contains": text}],
        },
        "response": {
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "jsonBody": {"total_hits": 0, "page": 1, "per_page": 10, "results": []},
            "fixedDelayMilliseconds": 1000,
        },
    }
