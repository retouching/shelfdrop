"""The follow-up of a download through the real API: the
state, the percent, the speed and the time left read from qBittorrent at each read, then the
download complete, which qBittorrent is not asked for again."""

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

pytestmark = [pytest.mark.downloads, pytest.mark.downloads_follow]


@pytest.mark.usefixtures("torrent_saved")
def test_a_download_shows_the_figures_of_qbittorrent_then_completes(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    data = torrent_file("Shelfdrop Follow Test T03")
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_search_stub(
                "Shelfdrop Follow Test",
                [7030],
                [
                    prowlarr_release(
                        "https://nyaa.test/view/9101", "Shelfdrop.Follow.Test.T03.CBZ", "follow-3"
                    )
                ],
            ),
            prowlarr_download_stub(1, "follow-3", data),
            *torrent_stubs(
                digest,
                "Shelfdrop Follow Test T03",
                added={"state": "downloading", "progress": 0.776, "dlspeed": 4404019, "eta": 96},
            ),
        ]
    )
    search = run_search(
        client,
        {
            "mode": "work",
            "kind": "manga",
            "title": "Shelfdrop Follow Test",
            "names": ["Shelfdrop Follow Test"],
        },
    )
    body = {
        "search_id": search["progress"]["id"],
        "series": "Shelfdrop Follow Test",
        "releases": [
            {"id": search["releases"][0]["id"], "volumes": {"kind": "single", "first": 3}}
        ],
    }
    created = client.post("/api/v1/downloads", json=body).json()["downloads"][0]

    found = wait_for_download(client, created["id"], lambda d: d["progress"]["state"] != "waiting")

    assert found["progress"] == {
        "state": "downloading",
        "percent": 77,
        "speed": 4404019,
        "eta": 96,
        "reason": None,
        "destination": None,
        "unplaced": None,
    }
    fake_sources.post(f"/tests/complete/{digest}")
    # Complete: its placement takes it (the worker of the test stack); its torrent lists no
    # file there, so it ends to place by hand.
    done = wait_for_download(
        client, created["id"], lambda d: d["progress"]["state"] not in ("downloading", "placing")
    )
    assert (done["progress"]["state"], done["progress"]["unplaced"]) == (
        "to_place",
        "missing_files",
    )
    # Ended: the next reads do not ask qBittorrent for it.
    fake_sources.reset_journal()
    again = client.get("/api/v1/downloads").json()["downloads"]
    assert next(d for d in again if d["id"] == created["id"])["progress"]["state"] == "to_place"
    asked = fake_sources.requests("GET", f"{QUI_PROXY}/torrents/info")
    assert all(digest not in r["url"] for r in asked)
