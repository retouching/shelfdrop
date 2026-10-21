"""The filters of the releases through the real API (section 3, point 12): rules with points,
a minimum score, an invalid rule refused."""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from tests.integration.support import run_search

pytestmark = [pytest.mark.releases, pytest.mark.releases_filters]

FRENCH = {"name": "Français", "pattern": r"\b(FRENCH|VF)\b", "regex": True, "score": 100}
ENGLISH = {"name": "Anglais", "pattern": "ENGLISH, 1r0n", "regex": False, "score": -50}


@pytest.fixture
def saved(client: httpx.Client) -> Iterator[dict[str, Any]]:
    before: dict[str, Any] = client.get("/api/v1/filters").json()
    yield before
    client.put("/api/v1/filters", json=before).raise_for_status()


def test_the_filters_score_and_set_aside(client: httpx.Client, saved: dict[str, Any]) -> None:
    assert saved == {"rules": [], "minimum": -100}
    response = client.put(
        "/api/v1/filters",
        json={"rules": [FRENCH, {**ENGLISH, "kinds": ["manga"]}], "minimum": -10},
    )
    assert response.status_code == 200
    assert response.json()["rules"][1]["kinds"] == ["manga"]

    body = run_search(
        client,
        {
            "mode": "work",
            "kind": "manga",
            "title": "Jujutsu Kaisen",
            "names": ["Jujutsu Kaisen", "Sorcery Fight"],
        },
    )

    by_title = {r["title"]: r for r in body["releases"]}
    french = by_title["Jujutsu.Kaisen.T02.FRENCH.MANGA.CBZ.eBook-PapriKa+"]
    assert (french["score"], french["rejected"]) == (100, None)
    assert french["score_rules"] == [{"name": "Français", "score": 100}]
    english = by_title["Jujutsu.Kaisen.T03.ENGLISH.CBZ-1r0n"]
    assert (english["score"], english["rejected"]) == (-50, "score")
    assert body["minimum"] == -10
    # Same volume, the score first: the French T01 before any other.
    t01 = [
        r
        for r in body["releases"]
        if r["volumes"]["first"] == 1 and r["volumes"]["kind"] == "single"
    ]
    assert t01[0]["score"] == 100


def test_the_score_follows_the_filters_of_now(client: httpx.Client, saved: dict[str, Any]) -> None:
    search = {
        "mode": "manual",
        "kind": "manga",
        "title": "Burn the Witch",
        "names": ["Burn the Witch"],
    }
    first = run_search(client, search)
    client.put("/api/v1/filters", json={"rules": [{**FRENCH, "pattern": r"\bFR\b"}], "minimum": 0})

    again = client.get(f"/api/v1/searches/{first['progress']['id']}").json()

    scores = {r["title"]: r["score"] for r in again["releases"]}
    assert scores["Burn.the.Witch.Kubo.2021.FR.[CBZ]-PapriKa"] == 100
    assert all(r["score"] == 0 for r in first["releases"])


def test_an_invalid_rule_is_refused_and_nothing_is_saved(
    client: httpx.Client, saved: dict[str, Any]
) -> None:
    response = client.put(
        "/api/v1/filters",
        json={"rules": [FRENCH, {**ENGLISH, "pattern": "(ENGLISH", "regex": True}], "minimum": 0},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "invalid_filter_rule",
        "detail": "A filter rule is empty or its expression is invalid",
        "data": {"positions": [1]},
    }
    assert client.get("/api/v1/filters").json() == saved
