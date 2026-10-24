"""The manual search through the real API: the text as typed, cleaned the same way,
sorted the same way, nothing set aside for its words."""

import httpx
import pytest

from tests.integration.support import FakeSources, run_search

pytestmark = [pytest.mark.releases, pytest.mark.releases_manual]


def test_the_text_is_searched_as_typed_without_the_relevance_filter(client: httpx.Client) -> None:
    body = run_search(
        client,
        {
            "mode": "manual",
            "kind": "manga",
            "title": "Tasogare Otome x Amnesia",
            "names": ["Tasogare Otome x Amnesia"],
        },
    )

    assert body["progress"]["mode"] == "manual"
    assert {r["title"] for r in body["releases"]} == {
        "Tasogare.Otome.x.Amnesia.T01.FRENCH.CBZ.eBook-PapriKa+",
        "Amnesia.T01.FRENCH.CBZ.eBook-NOTAG",
    }
    assert all(r["rejected"] is None for r in body["releases"])


def test_a_manual_search_is_cleaned_and_keeps_a_release_of_another_name(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    body = run_search(
        client,
        {
            "mode": "manual",
            "kind": "manga",
            "title": "Burn the Witch!",
            "names": ["Burn the Witch!"],
        },
    )

    assert fake_sources.prowlarr_searches("Burn the Witch")
    titles = [r["title"] for r in body["releases"]]
    assert "Burning Witch Hunter T01 FRENCH CBZ" in titles
    assert len(titles) == 3


def test_a_manual_search_has_one_text(client: httpx.Client) -> None:
    response = client.post(
        "/api/v1/searches",
        json={"mode": "manual", "kind": "manga", "title": "x", "names": ["Berserk", "Monster"]},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "too_many_names"


def test_a_text_without_two_letters_is_refused(client: httpx.Client) -> None:
    response = client.post(
        "/api/v1/searches", json={"mode": "manual", "kind": "manga", "title": "!", "names": ["!"]}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "query_too_short"
