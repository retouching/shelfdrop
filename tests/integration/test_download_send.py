"""The send of the releases of a work through the real API: the
torrent fetched through Prowlarr with its key in a header alone, its id, the add into the
category of its kind, the torrent looked for by its hash; a duplicate; the automatic rules;
the `.torrent` of a release. Prowlarr and qBittorrent (behind qui) are the fake sources."""

from typing import Any

import httpx
import pytest

from shelfdrop.utils.torrent import torrent_id
from tests.integration.support import (
    PROWLARR_KEY,
    QUI_PROXY,
    FakeSources,
    Stack,
    prowlarr_download_stub,
    prowlarr_release,
    prowlarr_search_stub,
    run_search,
    torrent_stubs,
    wait_for_download,
)
from tests.unit.support import torrent_file

pytestmark = [pytest.mark.downloads, pytest.mark.downloads_send]


def work_search(
    client: httpx.Client, fake_sources: FakeSources, name: str, releases: list[dict[str, Any]]
) -> dict[str, Any]:
    """The search of a work named `name`, Prowlarr answering `releases`."""
    fake_sources.load([prowlarr_search_stub(name, [7030], releases)])
    return run_search(client, {"mode": "work", "kind": "manga", "title": name, "names": [name]})


@pytest.mark.usefixtures("torrent_saved")
def test_a_release_of_a_work_is_sent_with_what_it_is_for_and_found_by_its_hash(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    title = "Shelfdrop.Send.Test.T01-T11.FRENCH.CBZ.eBook-PapriKa+"
    data = torrent_file("Shelfdrop Send Test T01-T11")
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_download_stub(1, "send-1", data),
            *torrent_stubs(digest, "Shelfdrop Send Test T01-T11"),
        ]
    )
    search = work_search(
        client,
        fake_sources,
        "Shelfdrop Send Test",
        [prowlarr_release("https://nyaa.test/view/9001", title, "send-1")],
    )
    release = search["releases"][0]
    # The download link of Prowlarr carries its key: never given to the page.
    assert "download_url" not in release
    assert PROWLARR_KEY not in str(search)
    assert release["automatic"] is True

    sent = client.post(
        "/api/v1/downloads",
        json={
            "search_id": search["progress"]["id"],
            "work_id": "mangaupdates:9001",
            "author": "Tatsuki Fujimoto",
            "series": "Shelfdrop Send Test",
            "releases": [
                {"id": release["id"], "volumes": {"kind": "range", "first": 1, "last": 11}}
            ],
        },
    )

    assert sent.status_code == 200, sent.text
    created = sent.json()["downloads"][0]
    assert created["progress"]["state"] == "waiting"
    found = wait_for_download(client, created["id"], lambda d: d["progress"]["state"] != "waiting")
    assert found["progress"]["state"] == "downloading"
    assert found["info_hash"] == digest
    assert {k: found[k] for k in ("mode", "kind", "category", "work_id", "author", "series")} == {
        "mode": "auto",
        "kind": "manga",
        "category": "manga",
        "work_id": "mangaupdates:9001",
        "author": "Tatsuki Fujimoto",
        "series": "Shelfdrop Send Test",
    }
    assert found["volumes"] == {"kind": "range", "first": 1, "last": 11}
    assert (found["created_by"], found["attempts"]) == ("admin", 1)
    # Prowlarr asked with its key in the header alone; qBittorrent given the file, into manga.
    asked = fake_sources.requests("GET", "/1/download")
    assert asked
    assert all("apikey" not in r["url"] for r in asked)
    headers = {name.lower(): value for name, value in asked[-1]["headers"].items()}
    assert headers["x-api-key"] == PROWLARR_KEY
    adds = [
        r
        for r in fake_sources.requests("POST", f"{QUI_PROXY}/torrents/add")
        if "Shelfdrop Send Test T01-T11" in r["body"]
    ]
    assert len(adds) == 1
    assert 'name="category"\r\n\r\nmanga\r\n' in adds[0]["body"]
    assert PROWLARR_KEY not in stack.api_logs()
    # Done: its torrent completes, the placement takes it (a torrent of no file here: to place).
    fake_sources.post(f"/tests/complete/{digest}")
    done = wait_for_download(
        client, created["id"], lambda d: d["progress"]["state"] != "downloading"
    )
    assert done["progress"]["state"] in ("placing", "to_place")


@pytest.mark.usefixtures("torrent_saved")
def test_a_torrent_already_in_qbittorrent_is_a_duplicate_never_sent_again(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    data = torrent_file("Shelfdrop Duplicate Test T01")
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_download_stub(1, "duplicate-1", data),
            {
                "priority": 1,
                "request": {
                    "method": "GET",
                    "urlPath": f"{QUI_PROXY}/torrents/info",
                    "queryParameters": {"hashes": {"equalTo": digest}},
                },
                "response": {
                    "status": 200,
                    "headers": {"Content-Type": "application/json"},
                    "jsonBody": [{"hash": digest, "state": "uploading", "progress": 1.0}],
                },
            },
        ]
    )
    search = work_search(
        client,
        fake_sources,
        "Shelfdrop Duplicate Test",
        [
            prowlarr_release(
                "https://nyaa.test/view/9002", "Shelfdrop.Duplicate.Test.T01.CBZ", "duplicate-1"
            )
        ],
    )
    body = {
        "search_id": search["progress"]["id"],
        "series": "Shelfdrop Duplicate Test",
        "releases": [
            {"id": search["releases"][0]["id"], "volumes": {"kind": "single", "first": 1}}
        ],
    }

    created = client.post("/api/v1/downloads", json=body).json()["downloads"][0]
    found = wait_for_download(client, created["id"], lambda d: d["progress"]["state"] == "failed")

    assert found["progress"]["reason"] == "duplicate"
    assert not [
        r
        for r in fake_sources.requests("POST", f"{QUI_PROXY}/torrents/add")
        if "Shelfdrop Duplicate Test T01" in r["body"]
    ]
    again = client.post(f"/api/v1/downloads/{created['id']}/retry")
    assert again.status_code == 409
    assert again.json()["code"] == "download_not_retryable"


def test_an_automatic_download_never_takes_a_tracker_not_allowed_nor_an_unknown_release(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    search = work_search(
        client,
        fake_sources,
        "Shelfdrop Refused Test",
        [
            prowlarr_release(
                "https://c411.test/t/9003",
                "Shelfdrop.Refused.Test.T01.FRENCH.CBZ",
                "refused-1",
                indexer_id=4,
                indexer="C411",
            )
        ],
    )
    release = search["releases"][0]
    # C411 is left out of the automatic downloads at the first read of the trackers.
    assert release["automatic"] is False
    body = {
        "search_id": search["progress"]["id"],
        "releases": [{"id": release["id"], "volumes": {"kind": "single", "first": 1}}],
    }

    refused = client.post("/api/v1/downloads", json=body)
    unknown = client.post(
        "/api/v1/downloads",
        json={**body, "releases": [{"id": "0" * 16, "volumes": {"kind": "unknown"}}]},
    )
    gone = client.post("/api/v1/downloads", json={**body, "search_id": "gone"})

    assert refused.status_code == 422
    assert refused.json() == {
        "code": "release_not_automatic",
        "detail": "Releases an automatic download may not take",
        "data": {"ids": [release["id"]]},
    }
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "release_not_in_search"
    assert gone.status_code == 404
    assert gone.json()["code"] == "search_not_found"
    assert not fake_sources.requests("GET", "/4/download")


def test_the_torrent_file_of_a_release_comes_through_prowlarr(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    data = torrent_file("Shelfdrop Torrent Test T01")
    fake_sources.load([prowlarr_download_stub(1, "file-1", data)])
    search = work_search(
        client,
        fake_sources,
        "Shelfdrop Torrent Test",
        [
            prowlarr_release(
                "https://nyaa.test/view/9004", "Shelfdrop.Torrent.Test.T01.CBZ", "file-1"
            )
        ],
    )

    response = client.get(f"/api/v1/releases/{search['releases'][0]['id']}/torrent")
    unknown = client.get(f"/api/v1/releases/{'0' * 16}/torrent")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-bittorrent"
    assert response.content == data
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "release_not_found"
