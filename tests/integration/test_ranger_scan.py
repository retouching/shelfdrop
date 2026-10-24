"""The scan of the libraries for the files misplaced, through the real image: asked by the page,
done by the worker; a file at the root of a library, a volume out of its name, a folder of chapters
already on the shelf; its time of the day saved."""

import httpx
import pytest

from tests.integration.ranger_support import MAKE_CBZ, named, wait_for_items
from tests.integration.support import Stack

pytestmark = [pytest.mark.ranger, pytest.mark.ranger_scan]


@pytest.mark.usefixtures("media")
def test_a_scan_asked_finds_the_files_misplaced_and_the_folders_of_chapters(
    client: httpx.Client, stack: Stack
) -> None:
    root = "/data/files/comics"
    series = "Shelfdrop Scan Test"
    stack.exec_placement(
        "python",
        "-c",
        MAKE_CBZ,
        f"{root}/{series} T01.cbz",
        f"{root}/{series}/{series} 2.cbz",
        f"{root}/{series}/{series} - T03.cbz",
        f"{root}/{series}/Chapitre 30.cbz",
        f"{root}/{series}/Chapitre 31.cbz",
    )

    assert client.post("/api/v1/place/scan").status_code == 202
    items = named(wait_for_items(client, lambda i: len(named(i, series)) == 3), series)

    assert sorted((i["name"], i["state"], i["reason"], i["origin"]) for i in items) == [
        (series, "chapters", "chapters", "library"),
        (f"{series} 2.cbz", "misplaced", "naming", "library"),
        (f"{series} T01.cbz", "misplaced", "root", "library"),
    ]
    [chapters] = [i for i in items if i["state"] == "chapters"]
    # The volumes of the folder, the one out of its name too.
    assert (chapters["chapters"], chapters["existing"]) == ([30, 31], [2, 3])

    stack.exec_placement("rm", f"{root}/{series} T01.cbz")
    assert client.post("/api/v1/place/scan").status_code == 202
    left = wait_for_items(client, lambda i: len(named(i, series)) == 2)
    assert f"{series} T01.cbz" not in [i["name"] for i in named(left, series)]


def test_the_time_of_the_daily_scan_is_a_setting(client: httpx.Client) -> None:
    saved = client.put("/api/v1/settings", json={"values": {"placement.scan_time": "05:15"}})
    assert saved.status_code == 200, saved.text
    refused = client.put("/api/v1/settings", json={"values": {"placement.scan_time": "25:00"}})
    assert refused.status_code == 422
    assert client.get("/api/v1/settings").json()["values"]["placement.scan_time"] == "05:15"
