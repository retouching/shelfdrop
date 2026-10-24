"""The waiting searches through the real API: one search for each
volume, never twice; the round of the API searches it under the names of the work, in the
queue of the other searches; a release that answers makes it found, on the page and on
Discord; nothing is downloaded; a removal leaves the list. Prowlarr and Discord are played by
the fake sources."""

import time
from typing import Any

import httpx
import pytest

from tests.integration.support import (
    FakeSources,
    prowlarr_release,
    prowlarr_search_stub,
    wait_for_messages,
)

pytestmark = [pytest.mark.waiting]


def wait_for_state(client: httpx.Client, waiting_id: int, state: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    entry: dict[str, Any] = {}
    while time.monotonic() < deadline:
        listed = client.get("/api/v1/waiting").json()["searches"]
        entry = next(e for e in listed if e["id"] == waiting_id)
        if entry["state"] == state and entry["attempts"] > 0:
            return entry
    return entry


@pytest.mark.usefixtures("webhook_saved")
def test_a_volume_waited_for_is_found_journaled_and_removed(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    name = "Shelfdrop Waiting Test"
    fake_sources.load(
        [
            prowlarr_search_stub(
                name,
                [7030],
                [
                    prowlarr_release(
                        "https://nyaa.test/view/waiting-t03",
                        "Shelfdrop.Waiting.Test.T03.FRENCH.CBZ",
                        "waiting-t03",
                    ),
                    prowlarr_release(
                        "https://nyaa.test/view/waiting-t02",
                        "Shelfdrop.Waiting.Test.T02.FRENCH.CBZ",
                        "waiting-t02",
                    ),
                ],
            )
        ]
    )
    body = {
        "work_id": None,
        "title": name,
        "author": "Shelfdrop Author",
        "kind": "manga",
        "names": [name],
        "wanted": [{"target": "volume", "volume": 3}, {"target": "volume", "volume": 4}],
    }

    added = client.post("/api/v1/waiting", json=body)
    again = client.post("/api/v1/waiting", json=body)

    assert added.status_code == 200, added.text
    assert [e["label"] for e in added.json()["added"]] == ["T03", "T04"]
    assert (again.json()["added"], again.json()["skipped"]) == ([], 2)
    t03, t04 = (e["id"] for e in added.json()["added"])
    found = wait_for_state(client, t03, "found")
    assert (found["state"], found["releases"]) == ("found", 1)
    assert wait_for_state(client, t04, "waiting")["state"] == "waiting"
    [message] = wait_for_messages(fake_sources, name)
    [embed] = message["embeds"]
    assert embed["title"] == f"Trouvé : {name}"
    assert "T03" in embed["description"]
    # Nothing is downloaded alone.
    assert all(d["work_name"] != name for d in client.get("/api/v1/downloads").json()["downloads"])

    searched = client.post(f"/api/v1/waiting/{t04}/search")
    assert searched.status_code == 200, searched.text
    assert searched.json()["attempts"] >= 2
    assert client.delete(f"/api/v1/waiting/{t04}").status_code == 204
    assert client.delete(f"/api/v1/waiting/{t04}").json()["code"] == "waiting_not_found"
    listed = client.get("/api/v1/waiting").json()
    assert [e["id"] for e in listed["searches"] if e["title"] == name] == [t03]
    assert listed["every_hours"] == 6


def test_a_wanted_without_its_number_is_refused(client: httpx.Client) -> None:
    refused = client.post(
        "/api/v1/waiting",
        json={"title": "x", "kind": "manga", "names": ["x"], "wanted": [{"target": "volume"}]},
    )

    assert refused.status_code == 422
