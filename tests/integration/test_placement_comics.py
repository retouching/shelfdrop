"""The placement of a manga through the real image (plan section 3, points 4 and 4 bis): the
worker completes a download, compares it with the shelf, links the volumes missing as
`<Series> - TXX.cbz` (hardlinks: the torrent seeds on), writes the cover of the series, tags
the torrent, has Jellyfin scan, locks the metadata, posts on the journal; a torrent with a book
without a volume is placed in part, the rest left to Ranger; a release in chapters goes to
Ranger. qBittorrent, Jellyfin and Discord are the fake sources; the files are
made in the volume of the worker."""

import json

import httpx
import pytest

from tests.integration.support import (
    QUI_PROXY,
    SEPARATOR,
    FakeSources,
    Stack,
    jellyfin_library_stubs,
    send_completed,
    wait_for_download,
    wait_for_messages,
    wait_for_requests,
)

pytestmark = [pytest.mark.placement, pytest.mark.placement_comics]

MAKE_CBZ = """
import pathlib, sys, zipfile
for path in sys.argv[1:]:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("002.jpg", b"\\xff\\xd8\\xff\\xe0" + p.name.encode())
        z.writestr("001.jpg", b"\\xff\\xd8\\xff\\xe0first-" + p.name.encode())
"""


@pytest.mark.usefixtures("media", "qbittorrent_saved", "jellyfin_saved", "webhook_saved")
def test_the_volumes_missing_are_linked_tagged_scanned_locked_and_journaled(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Place Test"
    torrent = f"/data/torrents/manga/{series} T01-T03"
    shelf = f"/data/files/comics/{series}"
    stack.exec_placement(
        "python",
        "-c",
        MAKE_CBZ,
        *(f"{torrent}/Shelfdrop.Place.Test.T0{n}.FRENCH.cbz" for n in (1, 2, 3)),
    )
    stack.exec_placement(
        "sh", "-c", f"mkdir -p '{shelf}' && printf mine > '{shelf}/{series} - T01.cbz'"
    )
    fake_sources.load(
        jellyfin_library_stubs(
            "comics",
            [
                {
                    "Id": f"place-t0{n}",
                    "Type": "Book",
                    "Name": f"Tome {n}",
                    "Path": f"/files/comics/{series}/{series} - T0{n}.cbz",
                }
                for n in (2, 3)
            ],
        )
    )

    download, digest = send_completed(
        client,
        fake_sources,
        name=series,
        kind="manga",
        content_path=torrent,
        volumes={"kind": "range", "first": 1, "last": 3},
        author="Tatsuki Fujimoto",
        title="Shelfdrop.Place.Test.T01-T03.FRENCH.CBZ",
    )

    placed = wait_for_download(
        client, download["id"], lambda d: d["progress"]["state"] in ("placed", "to_place")
    )
    assert placed["progress"]["state"] == "placed"
    assert placed["progress"]["destination"] == f"BD & Mangas{SEPARATOR}{series}"
    listing = stack.exec_placement("sh", "-c", f"cd '{shelf}' && ls -1 && cat '{series} - T01.cbz'")
    assert listing.stdout.splitlines() == [
        f"{series} - T01.cbz",
        f"{series} - T02.cbz",
        f"{series} - T03.cbz",
        "cover.jpg",
        "mine",
    ]
    inodes = stack.exec_placement(
        "stat",
        "-c",
        "%i %h",
        f"{shelf}/{series} - T02.cbz",
        f"{torrent}/Shelfdrop.Place.Test.T02.FRENCH.cbz",
    )
    [linked, seeding] = inodes.stdout.splitlines()
    # One file, two names: the torrent seeds on.
    assert linked == seeding
    assert linked.endswith(" 2")
    [tagged] = [
        r
        for r in fake_sources.requests("POST", f"{QUI_PROXY}/torrents/addTags")
        if digest in r["body"]
    ]
    assert "tags=plac%C3%A9" in tagged["body"]
    assert wait_for_requests(fake_sources, "POST", "/Items/lib-comics/Refresh")
    [locked] = wait_for_requests(fake_sources, "POST", "/Items/place-t02")
    body = json.loads(locked["body"])
    assert body["Name"] == f"{series} - T02"
    assert (body["SeriesName"], body["IndexNumber"]) == (series, 2)
    assert body["People"] == [{"Name": "Tatsuki Fujimoto", "Type": "Author", "Role": ""}]
    assert body["LockedFields"] == ["Cast", "Name"]
    [message] = wait_for_messages(fake_sources, f"BD & Mangas{SEPARATOR}{series}")
    [embed] = message["embeds"]
    assert embed["title"] == f"Rangé : BD & Mangas{SEPARATOR}{series}"
    assert {f["name"]: f["value"] for f in embed["fields"]} == {
        "Tomes": "T02 à T03",
        "Déjà présents": "T01",
    }
    assert embed["thumbnail"] == {"url": "attachment://cover.jpg"}


@pytest.mark.usefixtures("media", "qbittorrent_saved")
def test_a_release_in_chapters_is_left_to_ranger(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Chapters Test"
    torrent = f"/data/torrents/manga/{series}"
    stack.exec_placement(
        "python",
        "-c",
        MAKE_CBZ,
        *(f"{torrent}/{series} - Ch. {n}.cbz" for n in ("230", "231", "231.5", "233")),
    )

    download, _ = send_completed(
        client,
        fake_sources,
        name=series,
        kind="manga",
        content_path=torrent,
        volumes={"kind": "unknown"},
        author="Tatsuki Fujimoto",
    )

    left = wait_for_download(
        client, download["id"], lambda d: d["progress"]["state"] in ("placed", "to_place")
    )
    assert left["progress"]["state"] == "to_place"
    assert left["progress"]["unplaced"] == "chapters"
    shelf = stack.exec_placement("sh", "-c", f"ls '/data/files/comics/{series}' 2>&1 || true")
    assert "No such file" in shelf.stdout


@pytest.mark.usefixtures("media", "qbittorrent_saved")
def test_a_torrent_with_a_book_without_a_volume_is_placed_in_part(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Part Test"
    torrent = f"/data/torrents/manga/{series}"
    shelf = f"/data/files/comics/{series}"
    stack.exec_placement(
        "python",
        "-c",
        MAKE_CBZ,
        f"{torrent}/Shelfdrop.Part.Test.T01.FRENCH.cbz",
        f"{torrent}/Shelfdrop.Part.Test.T02.FRENCH.cbz",
        f"{torrent}/Shelfdrop Part Test - Bonus.cbz",
    )

    download, digest = send_completed(
        client,
        fake_sources,
        name=series,
        kind="manga",
        content_path=torrent,
        volumes={"kind": "unknown"},
        author="Tatsuki Fujimoto",
    )

    left = wait_for_download(
        client, download["id"], lambda d: d["progress"]["state"] in ("placed", "to_place")
    )
    # The volumes read are on the shelf; the download waits in Ranger for the rest.
    assert (left["progress"]["state"], left["progress"]["unplaced"]) == ("to_place", "no_volume")
    listing = stack.exec_placement("ls", "-1", shelf).stdout.splitlines()
    assert listing == [f"{series} - T01.cbz", f"{series} - T02.cbz", "cover.jpg"]
    assert not [
        r
        for r in fake_sources.requests("POST", f"{QUI_PROXY}/torrents/addTags")
        if digest in r["body"]
    ]
