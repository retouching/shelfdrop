"""A release in chapters linked to its volumes from Ranger, through the real image (plan
section 3, point 4 bis): a complete volume merged into one CBZ (its cover, its pages in the
order of the chapters, its ComicInfo.xml), an incomplete one placed as it is, the rest without a
volume; the download placed once nothing of it is left."""

import httpx
import pytest

from tests.integration.ranger_support import MAKE_CBZ, READ_CBZ, named, wait_for_items
from tests.integration.support import FakeSources, Stack, send_completed, wait_for_download

pytestmark = [pytest.mark.ranger, pytest.mark.ranger_chapters]


@pytest.mark.usefixtures("media", "qbittorrent_saved")
def test_chapters_linked_to_volumes_are_merged_placed_as_they_are_or_without_a_volume(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Merge Test"
    torrent = f"/data/torrents/manga/{series}"
    stack.exec_placement(
        "python",
        "-c",
        MAKE_CBZ,
        *(f"{torrent}/{series} - Ch. {n}.cbz" for n in ("1", "2", "2.5", "3", "5", "9")),
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
    [item] = named(wait_for_items(client, lambda i: bool(named(i, torrent))), torrent)
    assert (item["state"], item["reason"]) == ("chapters", "chapters")
    assert item["chapters"] == [1, 2, 2.5, 3, 5, 9]

    asked = client.post(
        f"/api/v1/place/items/{item['id'].removeprefix('item-')}/link",
        json={
            "type": "chapters",
            "work_id": None,
            "series": series,
            "author": "Shelfdrop Author",
            "summary": "Un résumé.",
            "volumes": [
                {"volume": 1, "first": 1, "last": 3},
                {"volume": 2, "first": 4, "last": 6},
            ],
            "rest": "place",
        },
    )
    assert asked.status_code == 202, asked.text

    [done] = named(
        wait_for_items(client, lambda i: named(i, torrent)[0]["state"] == "placed"), torrent
    )
    assert done["destination"].endswith(series)
    folder = f"/data/files/comics/{series}"
    assert stack.exec_placement("ls", "-1", folder).stdout.splitlines() == [
        f"{series} - Ch. 9.cbz",
        f"{series} - T01.cbz",
        f"{series} - T02 - Ch. 5.cbz",
        "cover.jpg",
    ]
    read = stack.exec_placement("python", "-c", READ_CBZ, f"{folder}/{series} - T01.cbz")
    [names, *info] = read.stdout.splitlines()
    assert names.split("|") == [f"{n:04d}.jpg" for n in range(9)] + ["ComicInfo.xml"]
    xml = "\n".join(info)
    assert f"<Series>{series}</Series>" in xml
    assert "<Number>1</Number>" in xml
    assert "<Writer>Shelfdrop Author</Writer>" in xml
    assert "<Summary>Un résumé.</Summary>" in xml
    assert "<PageCount>9</PageCount>" in xml
    assert '<Page Image="0" Type="FrontCover" />' in xml
    first = stack.exec_placement(
        "python",
        "-c",
        "import sys, zipfile; z = zipfile.ZipFile(sys.argv[1]);"
        " print([z.read(n)[4:] for n in z.namelist()[:3]])",
        f"{folder}/{series} - T01.cbz",
    )
    # The cover, then the pages of the first chapter in their order.
    assert first.stdout.strip() == str(
        [
            f"one-{series} - Ch. 1.cbz".encode(),
            f"one-{series} - Ch. 1.cbz".encode(),
            f"two-{series} - Ch. 1.cbz".encode(),
        ]
    )
    placed = wait_for_download(client, download["id"], lambda d: d["progress"]["state"] == "placed")
    assert placed["progress"]["state"] == "placed"
