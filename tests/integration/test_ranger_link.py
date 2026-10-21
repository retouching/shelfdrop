"""Ranger through the real image (plan section 3, point 5): a download the worker could not
place is listed with its files; each file linked to a work is placed by the worker as a
volume, hardlinked (the torrent seeds on); a name taken refuses, and nothing is replaced; a
file of the shelf searched is corrected, moved."""

import httpx
import pytest

from tests.integration.ranger_support import MAKE_CBZ, named, wait_for_items
from tests.integration.support import SEPARATOR, FakeSources, Stack, send_completed

pytestmark = [pytest.mark.ranger, pytest.mark.ranger_link]


@pytest.mark.usefixtures("media", "qbittorrent_saved")
def test_files_left_by_the_worker_are_linked_placed_refused_and_corrected(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Link Test"
    torrent = f"/data/torrents/manga/{series}"
    stack.exec_placement(
        "python", "-c", MAKE_CBZ, f"{torrent}/Prologue.cbz", f"{torrent}/Extra.cbz"
    )
    download, _ = send_completed(
        client,
        fake_sources,
        name=series,
        kind="manga",
        content_path=torrent,
        volumes={"kind": "unknown"},
        author="Shelfdrop Author",
    )

    items = named(wait_for_items(client, lambda i: len(named(i, torrent)) == 2), torrent)
    assert sorted((i["name"], i["state"], i["reason"], i["origin"]) for i in items) == [
        ("Extra.cbz", "unlinked", "no_volume", "download"),
        ("Prologue.cbz", "unlinked", "no_volume", "download"),
    ]
    [prologue] = [i for i in items if i["name"] == "Prologue.cbz"]
    [extra] = [i for i in items if i["name"] == "Extra.cbz"]
    volume = {
        "type": "volume",
        "kind": "manga",
        "work_id": None,
        "series": series,
        "author": "Shelfdrop Author",
        "volume": 3,
    }
    number = prologue["id"].removeprefix("item-")
    asked = client.post(f"/api/v1/place/items/{number}/link", json=volume)
    assert asked.status_code == 202, asked.text
    assert asked.json()["state"] == "placing"
    assert client.post(f"/api/v1/place/items/{number}/link", json=volume).json()["code"] == (
        "place_item_busy"
    )

    placed = wait_for_items(
        client, lambda i: named(i, f"{torrent}/Prologue.cbz")[0]["state"] == "placed"
    )
    [done] = named(placed, f"{torrent}/Prologue.cbz")
    assert done["destination"] == f"BD & Mangas{SEPARATOR}{series}"
    shelf = f"/data/files/comics/{series}/{series} - T03.cbz"
    inodes = stack.exec_placement("stat", "-c", "%i", shelf, f"{torrent}/Prologue.cbz")
    [linked, seeding] = inodes.stdout.splitlines()
    assert linked == seeding

    other = extra["id"].removeprefix("item-")
    assert client.post(f"/api/v1/place/items/{other}/link", json=volume).status_code == 202
    refused = wait_for_items(
        client, lambda i: named(i, f"{torrent}/Extra.cbz")[0]["error"] is not None
    )
    [left] = named(refused, f"{torrent}/Extra.cbz")
    assert (left["state"], left["error"]) == ("unlinked", "exists")
    again = stack.exec_placement("stat", "-c", "%i", shelf, f"{torrent}/Prologue.cbz")
    assert again.stdout == inodes.stdout

    found = wait_for_items(
        client, lambda i: any(x["id"].startswith("shelf-") for x in i), q=f"{series} - T03"
    )
    [shelved] = [x for x in found if x["id"].startswith("shelf-")]
    assert (shelved["state"], shelved["path"]) == ("placed", shelf)
    moved = client.post(
        f"/api/v1/place/shelf/{shelved['id'].removeprefix('shelf-')}/link",
        json={**volume, "volume": 4},
    )
    assert moved.status_code == 202, moved.text
    wait_for_items(client, lambda i: any(x["state"] == "placed" for x in named(i, shelf)))
    listing = stack.exec_placement("ls", "-1", f"/data/files/comics/{series}").stdout.splitlines()
    assert f"{series} - T04.cbz" in listing
    assert f"{series} - T03.cbz" not in listing
    assert download["id"] > 0
