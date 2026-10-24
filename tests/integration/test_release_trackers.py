"""The trackers read from Prowlarr through the real API (section 3, point 13): nothing written
in the code but the order of the first import and the default categories; the searches ask the
trackers chosen alone, in the categories chosen for each kind."""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from tests.integration.support import FakeSources, run_search

pytestmark = [pytest.mark.releases, pytest.mark.releases_trackers]


@pytest.fixture
def trackers(client: httpx.Client) -> Iterator[list[dict[str, Any]]]:
    """The trackers read from Prowlarr, put back as the first import left them."""
    read = client.post("/api/v1/trackers/refresh")
    assert read.status_code == 200
    found: list[dict[str, Any]] = read.json()["trackers"]
    yield found
    client.put(
        "/api/v1/trackers",
        json={
            "trackers": [
                {k: t[k] for k in ("indexer_id", "used", "auto", "categories")} for t in found
            ]
        },
    ).raise_for_status()


def test_the_trackers_come_from_prowlarr(
    client: httpx.Client, trackers: list[dict[str, Any]]
) -> None:
    assert [t["name"] for t in trackers] == [
        "Nyaa.si",
        "The Old School",
        "Abnormal",
        "YggTorrent",
        "C411",
    ]
    by_name = {t["name"]: t for t in trackers}
    assert by_name["C411"]["auto"] is False
    assert by_name["YggTorrent"]["prowlarr_enabled"] is False
    assert by_name["Nyaa.si"]["language"] == "en-US"
    assert "NZBgeek" not in by_name  # a Usenet indexer
    assert client.get("/api/v1/trackers").json()["trackers"] == trackers


def test_the_searches_ask_the_trackers_chosen_in_their_order(
    client: httpx.Client, fake_sources: FakeSources, trackers: list[dict[str, Any]]
) -> None:
    saved = client.put(
        "/api/v1/trackers",
        json={
            "trackers": [
                {"indexer_id": 4, "used": True, "auto": True},
                {"indexer_id": 1, "used": False, "auto": True},
            ]
        },
    ).json()["trackers"]
    assert [(t["name"], t["used"], t["auto"]) for t in saved[:2]] == [
        ("C411", True, True),
        ("Nyaa.si", False, False),
    ]

    body = run_search(
        client,
        {
            "mode": "manual",
            "kind": "manga",
            "title": "Jujutsu Kaisen",
            "names": ["Jujutsu Kaisen"],
            "refresh": True,
        },
    )

    asked = fake_sources.prowlarr_searches("Jujutsu Kaisen")[-1]
    assert sorted(asked["indexerIds"]) == ["2", "3", "4"]
    t01 = [r for r in body["releases"] if r["volumes"] == {"kind": "single", "first": 1, "last": 1}]
    assert t01[0]["indexer"] == "C411"
    assert t01[0]["indexer_rank"] == 0


def test_a_read_again_keeps_the_choices(
    client: httpx.Client, trackers: list[dict[str, Any]]
) -> None:
    client.put(
        "/api/v1/trackers", json={"trackers": [{"indexer_id": 2, "used": False, "auto": False}]}
    ).raise_for_status()

    again = client.post("/api/v1/trackers/refresh").json()["trackers"]

    assert again[0]["name"] == "The Old School"
    assert again[0]["used"] is False
    assert len(again) == len(trackers)


def test_the_categories_of_a_tracker_come_from_prowlarr(
    client: httpx.Client, trackers: list[dict[str, Any]]
) -> None:
    by_name = {t["name"]: t for t in trackers}
    nyaa = by_name["Nyaa.si"]
    # A category of its own (100000 and over) and a sub-category under the name of its parent.
    assert {"id": 100920, "name": "Literature"} in nyaa["available_categories"]
    assert {"id": 7030, "name": "Books/Comics"} in nyaa["available_categories"]
    # Never chosen: the default ones.
    assert nyaa["default_categories"] is True
    assert nyaa["categories"] == {"manga": [7030], "ebook": [7020], "audiobook": [3030]}


def test_a_tracker_searched_in_categories_of_its_own_is_asked_apart(
    client: httpx.Client, fake_sources: FakeSources, trackers: list[dict[str, Any]]
) -> None:
    literature = {"manga": [100920, 156719], "ebook": [], "audiobook": [3030]}
    saved = client.put(
        "/api/v1/trackers",
        json={
            "trackers": [{"indexer_id": 1, "used": True, "auto": True, "categories": literature}]
        },
    )
    assert saved.status_code == 200
    nyaa = saved.json()["trackers"][0]
    assert (nyaa["name"], nyaa["categories"], nyaa["default_categories"]) == (
        "Nyaa.si",
        literature,
        False,
    )
    before = len(fake_sources.prowlarr_searches("Jujutsu Kaisen"))

    body = run_search(
        client,
        {
            "mode": "manual",
            "kind": "manga",
            "title": "Jujutsu Kaisen",
            "names": ["Jujutsu Kaisen"],
            "refresh": True,
        },
    )

    asked = fake_sources.prowlarr_searches("Jujutsu Kaisen")[before:]
    assert sorted((a["categories"], sorted(a["indexerIds"])) for a in asked) == [
        (["100920", "156719"], ["1"]),
        (["7030"], ["2", "3", "4"]),
    ]
    titles = {r["title"] for r in body["releases"]}
    assert "Jujutsu Kaisen v27 (2025) (Digital) (1r0n)" in titles
    assert body["progress"]["names"][0]["found"] == 10


def test_a_category_a_tracker_does_not_know_is_refused(
    client: httpx.Client, trackers: list[dict[str, Any]]
) -> None:
    refused = client.put(
        "/api/v1/trackers",
        json={
            "trackers": [
                {
                    "indexer_id": 4,
                    "used": True,
                    "auto": True,
                    "categories": {"manga": [100920], "ebook": [7020], "audiobook": [3030]},
                }
            ]
        },
    )

    assert refused.status_code == 422
    assert refused.json()["code"] == "unknown_tracker_category"
    assert refused.json()["data"] == {"indexer_ids": [4]}
    assert client.get("/api/v1/trackers").json()["trackers"] == trackers
