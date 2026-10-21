"""What the tests of the page Ranger share: CBZ files made in the volume of the worker, and the
files of Ranger read until they match."""

import time
from collections.abc import Callable
from typing import Any

import httpx

# Two pages a CBZ, each holding its name and the one of its file.
MAKE_CBZ = """
import pathlib, sys, zipfile
for path in sys.argv[1:]:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("002.jpg", b"\\xff\\xd8\\xff\\xe0two-" + p.name.encode())
        z.writestr("001.jpg", b"\\xff\\xd8\\xff\\xe0one-" + p.name.encode())
"""
# The names of the entries of a CBZ, then its ComicInfo.xml.
READ_CBZ = """
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    print("|".join(z.namelist()))
    print(z.read("ComicInfo.xml").decode())
"""


def wait_for_items(
    client: httpx.Client,
    found: Callable[[list[dict[str, Any]]], bool],
    *,
    q: str = "",
    seconds: float = 30,
) -> list[dict[str, Any]]:
    """The files of Ranger (and of the shelf matching `q`), read until `found` holds them."""
    deadline = time.monotonic() + seconds
    while True:
        answer = client.get("/api/v1/place/items", params={"q": q})
        answer.raise_for_status()
        items: list[dict[str, Any]] = answer.json()["items"]
        if found(items) or time.monotonic() > deadline:
            return items
        time.sleep(0.5)


def named(items: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    return [i for i in items if text in i["name"] or text in i["path"]]
