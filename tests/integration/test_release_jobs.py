"""The searches shared, queued and kept, through the real API (plan 2.6): each test searches
texts of its own, with stubs of its own."""

import concurrent.futures
from typing import Any

import httpx
import pytest

from tests.integration.support import FakeSources, Stack, events, prowlarr_search_stub, run_search

pytestmark = [pytest.mark.releases, pytest.mark.releases_jobs]


def release(guid: str, title: str) -> dict[str, Any]:
    return {
        "guid": guid,
        "title": title,
        "indexerId": 2,
        "indexer": "The Old School",
        "size": 1000,
        "seeders": 3,
        "protocol": "torrent",
    }


def search(
    stack: Stack, headers: dict[str, str], names: list[str], *, refresh: bool = False
) -> dict[str, Any]:
    response = httpx.post(
        f"{stack.base_url}/api/v1/searches",
        headers=headers,
        json={
            "mode": "work",
            "kind": "manga",
            "title": names[0],
            "names": names,
            "refresh": refresh,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return body


def test_two_identical_searches_at_once_follow_one_search(
    stack: Stack, client: httpx.Client, fake_sources: FakeSources, signed_in: dict[str, str]
) -> None:
    name = "shared release 7d2e"
    fake_sources.load(
        [prowlarr_search_stub(name, [7030], [release("s1", f"{name} T01")], delay_ms=1500)]
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(lambda _: search(stack, signed_in, [name]), range(2))
    events(client, first["id"])

    assert first["id"] == second["id"]
    assert client.get(f"/api/v1/searches/{first['id']}").json()["progress"]["followers"] == 2
    assert len(fake_sources.prowlarr_searches(name)) == 1


def test_an_answer_is_kept_and_asked_again_on_refresh(
    stack: Stack, client: httpx.Client, fake_sources: FakeSources
) -> None:
    name = "kept release 91af"
    fake_sources.load([prowlarr_search_stub(name, [7030], [release("k1", f"{name} T01")])])

    first = run_search(client, {"mode": "work", "kind": "manga", "title": name, "names": [name]})
    again = run_search(
        client, {"mode": "work", "kind": "manga", "title": name, "names": ["KEPT.release 91af"]}
    )
    assert len(fake_sources.prowlarr_searches(name)) == 1
    assert again["progress"]["fetched_at"] == first["progress"]["fetched_at"]
    assert [r["id"] for r in again["releases"]] == [r["id"] for r in first["releases"]]

    run_search(
        client,
        {"mode": "work", "kind": "manga", "title": name, "names": [name], "refresh": True},
    )
    assert len(fake_sources.prowlarr_searches(name)) == 2


def test_two_prowlarr_searches_at_most_and_the_next_waits(
    stack: Stack, client: httpx.Client, fake_sources: FakeSources, signed_in: dict[str, str]
) -> None:
    names = ["queued one 3b7c", "queued two 3b7c", "queued three 3b7c"]
    fake_sources.load(
        [prowlarr_search_stub(n, [7030], [release(n, f"{n} T01")], delay_ms=1500) for n in names]
    )

    busy = search(stack, signed_in, names[:2])
    waiting = search(stack, signed_in, names[2:])

    assert waiting["state"] == "queued"
    assert waiting["queued_ahead"] == 1
    seen = events(client, waiting["id"])
    states = [data["state"] for name, data in seen if name == "progress"]
    assert states[0] == "queued"
    assert states[-1] == "done"
    assert "running" in states
    assert seen[-1][0] == "end"
    events(client, busy["id"])


def test_the_events_give_the_progress_name_by_name(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack, signed_in: dict[str, str]
) -> None:
    names = ["progress a 66de", "progress b 66de"]
    fake_sources.load(
        [
            prowlarr_search_stub(names[0], [7030], [release("p1", f"{names[0]} T01")]),
            prowlarr_search_stub(
                names[1], [7030], [release("p2", f"{names[1]} T02")], delay_ms=1000
            ),
        ]
    )

    started = search(stack, signed_in, names)
    seen = [data for name, data in events(client, started["id"]) if name == "progress"]

    last = seen[-1]
    assert [(n["name"], n["state"], n["found"]) for n in last["names"]] == [
        (names[0], "done", 1),
        (names[1], "done", 1),
    ]
    assert any([n["state"] for n in data["names"]] == ["done", "running"] for data in seen)


def test_an_unknown_search_is_a_404(client: httpx.Client) -> None:
    for path in ("/api/v1/searches/nope", "/api/v1/searches/nope/events"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["code"] == "search_not_found"
