"""A torrent qBittorrent accepts and loses, through the real API (plan section 3, points 2 and
3): looked for 3 times, then not received; Retry sends the same torrent again into the same
category, one more attempt."""

import httpx
import pytest

from shelfdrop.utils.torrent import torrent_id
from tests.integration.support import (
    QUI_PROXY,
    FakeSources,
    prowlarr_download_stub,
    prowlarr_release,
    prowlarr_search_stub,
    run_search,
    torrent_stubs,
    wait_for_download,
)
from tests.unit.support import torrent_file

pytestmark = [pytest.mark.downloads, pytest.mark.downloads_retry]


@pytest.mark.usefixtures("qbittorrent_saved")
def test_a_torrent_lost_is_not_received_then_sent_again_as_it_is(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    data = torrent_file("Shelfdrop Retry Test T05")
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_search_stub(
                "Shelfdrop Retry Test",
                [7030],
                [
                    prowlarr_release(
                        "https://nyaa.test/view/9201", "Shelfdrop.Retry.Test.T05.CBZ", "retry-5"
                    )
                ],
            ),
            prowlarr_download_stub(1, "retry-5", data),
            *torrent_stubs(digest, "Shelfdrop Retry Test T05", lost=True),
        ]
    )
    search = run_search(
        client,
        {
            "mode": "work",
            "kind": "manga",
            "title": "Shelfdrop Retry Test",
            "names": ["Shelfdrop Retry Test"],
        },
    )
    body = {
        "search_id": search["progress"]["id"],
        "series": "Shelfdrop Retry Test",
        "releases": [
            {"id": search["releases"][0]["id"], "volumes": {"kind": "single", "first": 5}}
        ],
    }
    created = client.post("/api/v1/downloads", json=body).json()["downloads"][0]

    lost = wait_for_download(client, created["id"], lambda d: d["progress"]["state"] != "waiting")
    assert lost["progress"] == {
        "state": "failed",
        "percent": None,
        "speed": None,
        "eta": None,
        "reason": "not_received",
    }
    looks = [
        r for r in fake_sources.requests("GET", f"{QUI_PROXY}/torrents/info") if digest in r["url"]
    ]
    # Once before the add (a duplicate?), 3 times after.
    assert len(looks) == 4

    retried = client.post(f"/api/v1/downloads/{created['id']}/retry")

    assert retried.status_code == 200, retried.text
    assert retried.json()["attempts"] == 2
    found = wait_for_download(client, created["id"], lambda d: d["progress"]["state"] != "waiting")
    assert found["progress"]["state"] == "downloading"
    adds = [
        r
        for r in fake_sources.requests("POST", f"{QUI_PROXY}/torrents/add")
        if "Shelfdrop Retry Test T05" in r["body"]
    ]
    assert len(adds) == 2
    assert all('name="category"\r\n\r\nmanga\r\n' in r["body"] for r in adds)
    # Prowlarr asked once: the torrent read the first time is sent again.
    assert sum("retry-5" in r["url"] for r in fake_sources.requests("GET", "/1/download")) == 1
    fake_sources.post(f"/tests/complete/{digest}")
    wait_for_download(client, created["id"], lambda d: d["progress"]["state"] == "placing")
