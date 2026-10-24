"""A manual download through the real API: into the category
`shelfdrop-manual`, without a work, an author nor a series, and to place in Ranger once
complete; a tracker not allowed for the automatic downloads is taken."""

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

pytestmark = [pytest.mark.downloads, pytest.mark.downloads_manual]


@pytest.mark.usefixtures("torrent_saved")
def test_a_manual_download_goes_to_its_category_and_ends_to_place(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    data = torrent_file("Shelfdrop Manual Test")
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_search_stub(
                "shelfdrop manual test",
                [7030],
                [
                    prowlarr_release(
                        "https://c411.test/t/9301",
                        "Shelfdrop.Manual.Test.Deluxe.CBZ",
                        "manual-1",
                        indexer_id=4,
                        indexer="C411",
                    )
                ],
            ),
            prowlarr_download_stub(4, "manual-1", data),
            *torrent_stubs(digest, "Shelfdrop Manual Test"),
        ]
    )
    search = run_search(
        client,
        {
            "mode": "manual",
            "kind": "manga",
            "title": "shelfdrop manual test",
            "names": ["shelfdrop manual test"],
        },
    )
    body = {
        "search_id": search["progress"]["id"],
        "work_id": "ignored",
        "author": "ignored",
        "series": "ignored",
        "releases": [{"id": search["releases"][0]["id"], "volumes": {"kind": "unknown"}}],
    }

    sent = client.post("/api/v1/downloads", json=body)

    assert sent.status_code == 200, sent.text
    created = sent.json()["downloads"][0]
    assert {
        k: created[k] for k in ("mode", "category", "work_id", "work_name", "author", "series")
    } == {
        "mode": "manual",
        "category": "shelfdrop-manual",
        "work_id": None,
        "work_name": "shelfdrop manual test",
        "author": "",
        "series": "",
    }
    wait_for_download(client, created["id"], lambda d: d["progress"]["state"] == "downloading")
    adds = [
        r
        for r in fake_sources.requests("POST", f"{QUI_PROXY}/torrents/add")
        if "Shelfdrop Manual Test" in r["body"]
    ]
    assert len(adds) == 1
    assert 'name="category"\r\n\r\nshelfdrop-manual\r\n' in adds[0]["body"]
    fake_sources.post(f"/tests/complete/{digest}")
    done = wait_for_download(
        client, created["id"], lambda d: d["progress"]["state"] != "downloading"
    )
    assert done["progress"]["state"] == "to_place"
