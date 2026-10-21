"""The page Métadonnées through the real API (plan section 3, point 8): the series of the fake
Jellyfin, a change of its fields, its summary and its image, locked; the cover.jpg written by
the placement worker; a scan and its progress."""

import base64
import json

import httpx
import pytest

from tests.integration.support import (
    FakeSources,
    Stack,
    jellyfin_library_stubs,
    json_response,
    wait_for_requests,
)

pytestmark = [pytest.mark.library]

JPEG = b"\xff\xd8\xff\xe0shelfdrop-library-test"
SERIES = "/files/comics/Shelfdrop Library Test"


def library_items() -> list[dict[str, object]]:
    return [
        {"Id": "lib-series", "Type": "Folder", "Name": "Shelfdrop Library Test", "Path": SERIES},
        {
            "Id": "lib-t01",
            "Type": "Book",
            "Name": "Shelfdrop Library Test - T01",
            "Path": f"{SERIES}/Shelfdrop Library Test - T01.cbz",
            "IndexNumber": 1,
            "ImageTags": {"Primary": "t"},
        },
    ]


@pytest.mark.usefixtures("media", "jellyfin_saved")
def test_a_series_is_read_changed_locked_and_its_cover_written(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    fake_sources.load(
        [
            *jellyfin_library_stubs("comics", library_items()),
            {
                "priority": 1,
                "request": {"method": "POST", "urlPath": "/Items/lib-series/Images/Primary"},
                "response": {"status": 204},
            },
            {
                "priority": 1,
                "request": {"method": "GET", "urlPath": "/Items/lib-t01/Images/Primary"},
                "response": {
                    "status": 200,
                    "base64Body": base64.b64encode(JPEG).decode(),
                    "headers": {"Content-Type": "image/jpeg"},
                },
            },
        ]
    )
    stack.exec_placement("mkdir", "-p", f"/data{SERIES}")

    listed = client.get("/api/v1/library/series")
    assert listed.status_code == 200, listed.text
    [series] = [s for s in listed.json()["series"] if s["id"] == "lib-series"]
    assert (series["kind"], series["volumes"], series["volumes_without_summary"]) == ("manga", 1, 1)
    image = client.get("/api/v1/library/items/lib-t01/image")
    assert (image.status_code, image.content) == (200, JPEG)

    changed = client.put(
        "/api/v1/library/series/lib-series",
        json={
            "name": "Shelfdrop Library Test",
            "authors": ["Tatsuki Fujimoto"],
            "year": 2018,
            "genres": ["Action"],
            "summary": "Denji.",
            "summary_to_volumes": True,
            "image": {"kind": "item", "item_id": "lib-t01"},
            "save_cover": True,
        },
    )

    assert changed.status_code == 200, changed.text
    [posted] = wait_for_requests(fake_sources, "POST", "/Items/lib-series")
    body = json.loads(posted["body"])
    assert (body["Overview"], body["ProductionYear"]) == ("Denji.", 2018)
    assert body["LockedFields"] == ["Cast", "Genres", "Name", "Overview"]
    [volume] = wait_for_requests(fake_sources, "POST", "/Items/lib-t01")
    assert json.loads(volume["body"])["Overview"] == "Denji."
    [sent] = fake_sources.requests("POST", "/Items/lib-series/Images/Primary")
    assert base64.b64decode(sent["body"]) == JPEG
    # The worker writes the cover.jpg of the series within a round.
    written = ""
    for _ in range(30):
        written = stack.exec_placement(
            "sh", "-c", f"base64 -w0 '/data{SERIES}/cover.jpg' 2>/dev/null || true"
        ).stdout
        if written:
            break
    assert base64.b64decode(written) == JPEG

    refused = client.put(
        "/api/v1/library/series/lib-series",
        json={"name": "x", "image": {"kind": "data", "data": base64.b64encode(b"<svg/>").decode()}},
    )
    assert (refused.status_code, refused.json()["code"]) == (422, "image_refused")
    missing = client.put("/api/v1/library/series/nope", json={"name": "x"})
    assert (missing.status_code, missing.json()["code"]) == (404, "series_not_found")


@pytest.mark.usefixtures("jellyfin_saved")
def test_a_scan_is_asked_and_its_progress_read(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    fake_sources.load(
        [
            {
                "priority": 1,
                "request": {"method": "POST", "urlPath": "/Items/lib-comics/Refresh"},
                "response": {"status": 204},
            },
            {
                "priority": 1,
                "request": {"method": "GET", "urlPath": "/Library/VirtualFolders"},
                "response": json_response(
                    [
                        {
                            "Name": "BD & Mangas",
                            "CollectionType": "books",
                            "ItemId": "lib-comics",
                            "Locations": ["/files/comics"],
                            "RefreshStatus": "Active",
                            "RefreshProgress": 42.5,
                        }
                    ]
                ),
            },
        ]
    )

    started = client.post("/api/v1/library/scan", json={"mode": "missing", "kind": "manga"})

    assert started.status_code == 202, started.text
    assert started.json()["progress"] == {"manga": 42.5}
    [refresh] = fake_sources.requests("POST", "/Items/lib-comics/Refresh")
    assert "metadataRefreshMode=FullRefresh" in refresh["url"]
