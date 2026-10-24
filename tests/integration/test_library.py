"""The page Jellyfin through the real API: the series of the fake
Jellyfin, a change of its fields, its summary and its image, locked; the cover.jpg written by
the placement worker; the images kept by the browser with their tag; the refresh of Jellyfin
after each change; a scan and its progress; the volumes of a series, the file of one
downloaded, one changed; the sync of the metadata of a file placed."""

import base64
import json
import time

import httpx
import pytest

from tests.integration.ranger_support import MAKE_CBZ, named, wait_for_items
from tests.integration.support import (
    FakeSources,
    Stack,
    jellyfin_file_stubs,
    jellyfin_library_stubs,
    json_response,
    wait_for_requests,
)

pytestmark = [pytest.mark.library]

JPEG = b"\xff\xd8\xff\xe0shelfdrop-library-test"
SERIES = "/files/comics/Shelfdrop Library Test"
# The parameters of the refresh after a change: nothing written is replaced (F40).
AFTER_CHANGE = (
    "metadataRefreshMode=FullRefresh",
    "imageRefreshMode=Default",
    "replaceAllMetadata=false",
    "replaceAllImages=false",
)


def refreshed_after_change(fake_sources: FakeSources, item_id: str) -> None:
    """The item was refreshed once after its change, in the mode that keeps what was written."""
    [refresh] = wait_for_requests(fake_sources, "POST", f"/Items/{item_id}/Refresh")
    assert all(parameter in refresh["url"] for parameter in AFTER_CHANGE), refresh["url"]


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
            *jellyfin_library_stubs("ebooks", []),
            *jellyfin_library_stubs("audiobooks", []),
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
    assert image.headers["Cache-Control"] == "private, max-age=60"
    # With its tag, the address changes with the image: the browser keeps it for good.
    tagged = client.get("/api/v1/library/items/lib-t01/image", params={"tag": "t"})
    assert (tagged.status_code, tagged.content) == (200, JPEG)
    assert tagged.headers["Cache-Control"] == "private, max-age=31536000, immutable"

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
    # The folder of the series refreshed, its volumes with it; not each volume.
    refreshed_after_change(fake_sources, "lib-series")
    assert fake_sources.requests("POST", "/Items/lib-t01/Refresh") == []
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
    # Neither refused change refreshed anything.
    assert len(fake_sources.requests("POST", "/Items/lib-series/Refresh")) == 1


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


VOLUMES = "/files/comics/Shelfdrop Volumes Test"
CBZ = b"PK\x03\x04shelfdrop-volumes-test" * 64


def volume_items() -> list[dict[str, object]]:
    return [
        {"Id": "vol-series", "Type": "Folder", "Name": "Shelfdrop Volumes Test", "Path": VOLUMES},
        {
            "Id": "vol-t01",
            "Type": "Book",
            "Name": "Shelfdrop Volumes Test - T01",
            "Path": f"{VOLUMES}/Shelfdrop Volumes Test - T01.cbz",
            "IndexNumber": 1,
            "ImageTags": {"Primary": "t"},
            "People": [{"Name": "Other", "Type": "Author"}],
        },
        {
            "Id": "vol-t03",
            "Type": "Book",
            "Name": "Shelfdrop Volumes Test - T03",
            "Path": f"{VOLUMES}/Shelfdrop Volumes Test - T03.cbz",
            "IndexNumber": 3,
        },
    ]


@pytest.mark.usefixtures("jellyfin_saved")
def test_the_volumes_of_a_series_are_listed_downloaded_and_changed(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    fake_sources.load(
        [
            *jellyfin_library_stubs("comics", volume_items()),
            *jellyfin_library_stubs("ebooks", []),
            *jellyfin_library_stubs("audiobooks", []),
            *jellyfin_file_stubs("vol-t01", CBZ),
        ]
    )

    listed = client.get("/api/v1/library/series/vol-series/volumes")

    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["series"]["id"] == "vol-series"
    assert [(v["id"], v["number"], v["file_name"], v["size"]) for v in body["volumes"]] == [
        ("vol-t01", 1, "Shelfdrop Volumes Test - T01.cbz", len(CBZ)),
        # Jellyfin sends no file for it: no size.
        ("vol-t03", 3, "Shelfdrop Volumes Test - T03.cbz", None),
    ]
    assert body["missing"] == [2]
    assert [v["image_tag"] for v in body["volumes"]] == ["t", None]

    downloaded = client.get("/api/v1/library/items/vol-t01/file")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == CBZ
    assert downloaded.headers["Content-Disposition"] == (
        'attachment; filename="Shelfdrop Volumes Test - T01.cbz"; '
        "filename*=UTF-8''Shelfdrop%20Volumes%20Test%20-%20T01.cbz"
    )
    # A folder is no file of a volume: Jellyfin is not asked for it.
    refused = client.get("/api/v1/library/items/vol-series/file")
    assert (refused.status_code, refused.json()["code"]) == (404, "volume_not_found")
    assert fake_sources.requests("GET", "/Items/vol-series/Download") == []

    changed = client.put(
        "/api/v1/library/items/vol-t01",
        json={
            "name": "Shelfdrop Volumes Test - T01 - Le début",
            "number": 1,
            "summary": "Le premier tome.",
            "authors": ["Shelfdrop Author"],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["id"] == "vol-t01"
    [posted] = wait_for_requests(fake_sources, "POST", "/Items/vol-t01")
    sent = json.loads(posted["body"])
    assert (sent["Name"], sent["IndexNumber"], sent["Overview"]) == (
        "Shelfdrop Volumes Test - T01 - Le début",
        1,
        "Le premier tome.",
    )
    assert sent["People"] == [{"Name": "Shelfdrop Author", "Type": "Author", "Role": ""}]
    assert sent["LockedFields"] == ["Cast", "Name", "Overview"]
    refreshed_after_change(fake_sources, "vol-t01")
    missing = client.put("/api/v1/library/items/nope", json={"name": "x"})
    assert (missing.status_code, missing.json()["code"]) == (404, "volume_not_found")


SYNC_SERIES = "Shelfdrop Sync Test"


@pytest.mark.usefixtures("media", "jellyfin_saved")
def test_a_sync_sends_the_metadata_of_a_file_placed_with_its_authors(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    folder = f"/files/comics/{SYNC_SERIES}"
    items: list[dict[str, object]] = [
        {"Id": "sync-series", "Type": "Folder", "Name": SYNC_SERIES, "Path": folder},
        {
            "Id": "sync-t01",
            "Type": "Book",
            "Name": "Tome 1",
            "Path": f"{folder}/{SYNC_SERIES} - T01.cbz",
            "People": [{"Name": "Jellyfin Author", "Type": "Author"}],
            "ImageTags": {"Primary": "t"},
        },
    ]
    fake_sources.load(
        [
            *jellyfin_library_stubs("comics", items),
            *jellyfin_library_stubs("ebooks", []),
            *jellyfin_library_stubs("audiobooks", []),
        ]
    )
    # The lock of the worker off: the sync asked runs all the same.
    settings = client.put("/api/v1/settings", json={"values": {"placement.lock_jellyfin": False}})
    settings.raise_for_status()
    try:
        root = "/data/files/comics"
        stack.exec_placement("python", "-c", MAKE_CBZ, f"{root}/{SYNC_SERIES} T01.cbz")
        assert client.post("/api/v1/place/scan").status_code == 202
        [found] = named(
            wait_for_items(client, lambda i: len(named(i, SYNC_SERIES)) == 1), SYNC_SERIES
        )
        link = {
            "type": "volume",
            "kind": "manga",
            "work_id": None,
            "series": SYNC_SERIES,
            "author": "Shelfdrop Sync Author",
            "volume": 1,
        }
        number = found["id"].removeprefix("item-")
        assert client.post(f"/api/v1/place/items/{number}/link", json=link).status_code == 202
        wait_for_items(client, lambda i: any(x["state"] == "placed" for x in named(i, SYNC_SERIES)))

        started = client.post("/api/v1/library/sync", json={"series_id": "sync-series"})
        assert started.status_code == 202, started.text
        assert started.json()["stage"] in ("running", "done")
        state = started.json()
        deadline = time.monotonic() + 30
        while state["stage"] == "running" and time.monotonic() < deadline:
            state = client.get("/api/v1/library/sync").json()

        assert (state["stage"], state["changed"], state["not_found"]) == ("done", 1, 0)
        [posted] = fake_sources.requests("POST", "/Items/sync-t01")
        sent = json.loads(posted["body"])
        assert (sent["Name"], sent["SeriesName"], sent["IndexNumber"]) == (
            f"{SYNC_SERIES} - T01",
            SYNC_SERIES,
            1,
        )
        # The authors of shelfdrop over those of Jellyfin; the image of the volume left.
        assert sent["People"] == [{"Name": "Shelfdrop Sync Author", "Type": "Author", "Role": ""}]
        assert sent["LockedFields"] == ["Cast", "Name"]
        assert fake_sources.requests("POST", "/Items/sync-t01/Images/Primary") == []
        # The folder of the series refreshed once, not the volume (F40).
        refreshed_after_change(fake_sources, "sync-series")
        assert fake_sources.requests("POST", "/Items/sync-t01/Refresh") == []
        unknown = client.post("/api/v1/library/sync", json={"series_id": "nope"})
        assert (unknown.status_code, unknown.json()["code"]) == (404, "series_not_found")
    finally:
        client.put(
            "/api/v1/settings", json={"values": {"placement.lock_jellyfin": True}}
        ).raise_for_status()
