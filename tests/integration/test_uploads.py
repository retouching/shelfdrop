"""The files sent from the page Manuel through the real image (plan section 3, point 6): a file
of more than one chunk of 50 MiB sent, resumed after a cut, put together and checked by its
SHA-256, then taken by the worker into Ranger and placed from there; a ZIP opened into its
books; a corrupt file removed; a file of another type or too big refused."""

import hashlib
import io
import os
import zipfile

import httpx
import pytest

from tests.integration.ranger_support import named, wait_for_items
from tests.integration.support import Stack

pytestmark = pytest.mark.uploads

MIB = 1024 * 1024


def cbz_of(size: int) -> bytes:
    """A CBZ of about `size` bytes: one page of random bytes, stored."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("001.jpg", b"\xff\xd8\xff\xe0" + os.urandom(size))
    return buffer.getvalue()


def start(client: httpx.Client, name: str, size: int) -> httpx.Response:
    return client.post("/api/v1/uploads", json={"name": name, "size": size})


def put(client: httpx.Client, upload_id: int, index: int, data: bytes) -> httpx.Response:
    return client.put(
        f"/api/v1/uploads/{upload_id}/chunks/{index}",
        content=data,
        headers={"Content-Type": "application/octet-stream"},
        timeout=120,
    )


def finish(client: httpx.Client, upload_id: int, data: bytes) -> httpx.Response:
    digest = hashlib.sha256(data).hexdigest()
    return client.post(f"/api/v1/uploads/{upload_id}/finish", json={"sha256": digest}, timeout=120)


@pytest.mark.usefixtures("media")
def test_a_file_sent_in_chunks_is_resumed_checked_taken_into_ranger_and_placed(
    client: httpx.Client, stack: Stack
) -> None:
    series = "Shelfdrop Upload Test"
    name = f"{series} T02.cbz"
    data = cbz_of(50 * MIB + 1000)
    started = start(client, name, len(data))
    assert started.status_code == 201, started.text
    upload = started.json()
    assert (upload["chunk_size"], upload["chunks"], upload["received"]) == (50 * MIB, 2, [])

    assert put(client, upload["id"], 0, data[: 50 * MIB]).json()["received"] == [0]
    resumed = start(client, name, len(data))
    assert resumed.status_code == 200
    assert (resumed.json()["id"], resumed.json()["received"]) == (upload["id"], [0])
    short = put(client, upload["id"], 1, data[50 * MIB : -1])
    assert (short.status_code, short.json()["code"]) == (422, "chunk_refused")
    assert put(client, upload["id"], 1, data[50 * MIB :]).json()["received"] == [0, 1]
    checked = finish(client, upload["id"], data)
    assert checked.status_code == 200, checked.text
    assert checked.json()["state"] == "verified"

    [item] = named(wait_for_items(client, lambda i: bool(named(i, name))), name)
    assert (item["origin"], item["kind"], item["state"], item["size"]) == (
        "upload",
        "manga",
        "unlinked",
        len(data),
    )
    assert item["path"] == f"/data/envois/{upload['id']}/{name}"
    asked = client.post(
        f"/api/v1/place/items/{item['id'].removeprefix('item-')}/link",
        json={
            "type": "volume",
            "kind": "manga",
            "work_id": None,
            "series": series,
            "author": "Shelfdrop Author",
            "volume": 2,
        },
    )
    assert asked.status_code == 202, asked.text
    wait_for_items(client, lambda i: named(i, name)[0]["state"] == "placed")
    shelf = f"/data/files/comics/{series}/{series} - T02.cbz"
    summed = stack.exec_placement("sha256sum", shelf).stdout.split()[0]
    assert summed == hashlib.sha256(data).hexdigest()
    left = stack.exec_placement("ls", "-A", "/data/envois").stdout.split()
    assert str(upload["id"]) not in left


@pytest.mark.usefixtures("media")
def test_a_zip_sent_gives_each_of_its_books(client: httpx.Client) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Lot/Shelfdrop Zip One.epub", b"one")
        archive.writestr("Lot/Shelfdrop Zip Two.cbz", cbz_of(10))
    data = buffer.getvalue()
    upload = start(client, "Shelfdrop Lot.zip", len(data)).json()
    put(client, upload["id"], 0, data).raise_for_status()
    finish(client, upload["id"], data).raise_for_status()

    items = named(
        wait_for_items(client, lambda i: len(named(i, "Shelfdrop Zip")) == 2), "Shelfdrop Zip"
    )
    assert sorted((i["name"], i["kind"], i["origin"]) for i in items) == [
        ("Shelfdrop Zip One.epub", "ebook", "upload"),
        ("Shelfdrop Zip Two.cbz", "manga", "upload"),
    ]


def test_a_corrupt_file_is_removed_and_a_file_refused_is_never_started(
    client: httpx.Client,
) -> None:
    data = cbz_of(100)
    upload = start(client, "Shelfdrop Corrupt.cbz", len(data)).json()
    put(client, upload["id"], 0, data).raise_for_status()

    corrupt = finish(client, upload["id"], data + b"x")
    again = put(client, upload["id"], 0, data)
    other = start(client, "Shelfdrop.exe", 10)
    big = start(client, "Shelfdrop Big.cbz", 5 * 1024 * MIB + 1)
    unknown = put(client, 999_999, 0, b"x")

    assert (corrupt.status_code, corrupt.json()["code"]) == (422, "upload_corrupt")
    assert (again.status_code, again.json()["code"]) == (409, "upload_done")
    assert (other.status_code, other.json()["code"], other.json()["data"]) == (
        422,
        "upload_refused",
        {"reason": "type"},
    )
    assert big.json()["data"] == {"reason": "size"}
    assert (unknown.status_code, unknown.json()["code"]) == (404, "upload_not_found")
