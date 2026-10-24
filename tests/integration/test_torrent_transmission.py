"""A real Transmission (the service `transmission` of the test stack) as the torrent client of
the settings: the test of its connection through the API, with its credentials; a release sent
from a search into the folder of its kind under the label of its category, complete at once
(its data already there), placed by the worker, which leaves its mark, the label `placé`, next
to the label of the category. Prowlarr and Jellyfin are the fake sources; Transmission has no
way out (a network of its own with the API and the fake sources)."""

import base64
import hashlib
import json
from collections.abc import Iterator
from typing import Any, Final

import httpx
import pytest

from shelfdrop.utils.torrent import torrent_id
from tests.integration.support import (
    FakeSources,
    Stack,
    compose,
    jellyfin_library_stubs,
    prowlarr_download_stub,
    prowlarr_release,
    prowlarr_search_stub,
    run_search,
    wait_for_download,
)
from tests.unit.support import bencode

pytestmark = [pytest.mark.torrents, pytest.mark.torrent_transmission]

# The address and the credentials of the service `transmission` (docker/compose.test.yaml).
TRANSMISSION_URL: Final = "http://transmission:9091"
TRANSMISSION_USER: Final = "shelfdrop"
TRANSMISSION_PASSWORD: Final = "transmission-password-of-the-tests"
# The folders of the kinds in Transmission, on the volume it shares with the placement worker.
FOLDERS: Final = {
    "manga": "/data/torrents/transmission/manga",
    "audiobook": "/data/torrents/transmission/audiobooks",
}
PIECE_LENGTH: Final = 16384
MARK_READ_ATTEMPTS: Final = 20

MAKE_CBZ = """
import pathlib, sys, zipfile
p = pathlib.Path(sys.argv[1])
p.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(p, "w") as z:
    z.writestr("001.jpg", b"\\xff\\xd8\\xff\\xe0first-" + p.name.encode())
    z.writestr("002.jpg", b"\\xff\\xd8\\xff\\xe0" + p.name.encode())
"""

# The RPC of Transmission asked from its own container: the session id taken from the 409, the
# credentials of the tests; the answer printed.
RPC = """
import base64, json, sys, urllib.error, urllib.request
auth = "Basic " + base64.b64encode(sys.argv[1].encode()).decode()
session = ""
for _ in range(2):
    request = urllib.request.Request(
        "http://127.0.0.1:9091/transmission/rpc", data=sys.argv[2].encode(), method="POST"
    )
    request.add_header("Authorization", auth)
    request.add_header("X-Transmission-Session-Id", session)
    try:
        with urllib.request.urlopen(request) as response:
            print(response.read().decode())
            break
    except urllib.error.HTTPError as error:
        if error.code != 409:
            raise
        session = error.headers["X-Transmission-Session-Id"]
"""


def transmission_rpc(stack: Stack, method: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """The `arguments` of the answer of the real Transmission to `method`."""
    body = json.dumps({"method": method, "arguments": arguments})
    credentials = f"{TRANSMISSION_USER}:{TRANSMISSION_PASSWORD}"
    result = compose(
        stack.project, "exec", "-T", "transmission", "python3", "-c", RPC, credentials, body
    )
    assert result.returncode == 0, result.stderr
    answer: dict[str, Any] = json.loads(result.stdout)
    assert answer["result"] == "success", answer
    found: dict[str, Any] = answer["arguments"]
    return found


def torrent_of_files(name: str, data: bytes) -> tuple[bytes, str]:
    """The `.torrent` of one file `name` holding `data`, with the hashes of its pieces (the
    client verifies them on the data in place), and its info hash."""
    pieces = b"".join(
        hashlib.sha1(data[i : i + PIECE_LENGTH], usedforsecurity=False).digest()
        for i in range(0, len(data), PIECE_LENGTH)
    )
    info: dict[str, Any] = {
        "name": name,
        "length": len(data),
        "piece length": PIECE_LENGTH,
        "pieces": pieces,
    }
    torrent = bencode({"announce": "http://tracker.invalid/announce", "info": info})
    digest = torrent_id(torrent)
    assert digest is not None
    return torrent, digest


def probe(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/v1/settings/test", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


@pytest.fixture
def transmission_saved(client: httpx.Client) -> Iterator[None]:
    """Transmission saved as the torrent client, with its credentials and the folders of the
    kinds, then qui again (the client of the other tests)."""
    values: dict[str, str | None] = {
        "torrent.client": "transmission",
        "torrent.url": TRANSMISSION_URL,
        "torrent.username": TRANSMISSION_USER,
        **{f"torrent.folder.{kind}": folder for kind, folder in FOLDERS.items()},
    }
    saved = {"values": values, "secrets": {"torrent.password": TRANSMISSION_PASSWORD}}
    client.put("/api/v1/settings", json=saved).raise_for_status()
    yield
    cleared = {
        "values": {**dict.fromkeys(values), "torrent.client": "qui"},
        "secrets": {"torrent.password": None},
    }
    client.put("/api/v1/settings", json=cleared).raise_for_status()


@pytest.mark.usefixtures("transmission_saved")
def test_transmission_is_tested_through_the_settings_with_its_credentials(
    client: httpx.Client,
) -> None:
    saved = probe(client, {"service": "torrent"})
    wrong = probe(client, {"service": "torrent", "secret": "a-wrong-password"})

    assert saved["ok"] is True
    assert saved["state"] == "connected"
    assert saved["version"] == "4.1.3"
    # Its labels exist once a torrent carries them: none is missing.
    assert (saved["count"], saved["missing"]) == (4, [])
    assert (wrong["state"], wrong["status"]) == ("refused", 401)


@pytest.mark.usefixtures("media", "transmission_saved", "jellyfin_saved")
def test_a_release_sent_to_transmission_goes_into_the_folder_of_its_kind_under_its_label(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Transmission Test"
    name = "Shelfdrop.Transmission.Test.T01.FRENCH.cbz"
    content = f"{FOLDERS['manga']}/{name}"
    shelf = f"/data/files/comics/{series}"
    # Its data already in the folder of the kind: Transmission verifies it, complete at once.
    stack.exec_placement("python", "-c", MAKE_CBZ, content)
    data = base64.b64decode(stack.exec_placement("base64", "-w0", content).stdout)
    torrent, digest = torrent_of_files(name, data)
    fake_sources.load(
        [
            prowlarr_search_stub(
                series,
                [7030],
                [
                    prowlarr_release(
                        "https://nyaa.test/view/transmission-1",
                        "Shelfdrop.Transmission.Test.T01.FRENCH.CBZ",
                        "transmission-1",
                    )
                ],
            ),
            prowlarr_download_stub(1, "transmission-1", torrent),
            *jellyfin_library_stubs("comics", []),
        ]
    )
    search = run_search(
        client, {"mode": "work", "kind": "manga", "title": series, "names": [series]}
    )
    sent = client.post(
        "/api/v1/downloads",
        json={
            "search_id": search["progress"]["id"],
            "work_id": None,
            "author": "Tatsuki Fujimoto",
            "series": series,
            "releases": [
                {"id": search["releases"][0]["id"], "volumes": {"kind": "single", "first": 1}}
            ],
        },
    )
    assert sent.status_code == 200, sent.text
    download = sent.json()["downloads"][0]

    placed = wait_for_download(
        client, download["id"], lambda d: d["progress"]["state"] in ("placed", "to_place")
    )

    assert placed["info_hash"] == digest
    assert placed["category"] == "manga"
    # The file of a torrent of one file, as Transmission gives it: the worker linked it.
    assert placed["progress"]["state"] == "placed"
    inodes = stack.exec_placement(
        "stat", "-c", "%i", f"{shelf}/{series} - T01.cbz", content
    ).stdout.split()
    assert len(set(inodes)) == 1
    # The mark follows the placement: read again (each read is a Compose call, no sleep).
    fields = ["hashString", "downloadDir", "labels", "percentDone", "status", "files"]
    for _ in range(MARK_READ_ATTEMPTS):
        [seen] = transmission_rpc(stack, "torrent-get", {"ids": [digest], "fields": fields})[
            "torrents"
        ]
        if "placé" in seen["labels"]:
            break
    assert seen["downloadDir"] == FOLDERS["manga"]
    assert seen["percentDone"] == 1
    assert seen["status"] == 6
    assert [f["name"] for f in seen["files"]] == [name]
    # The label of its category, and the mark of shelfdrop next to it.
    assert seen["labels"] == ["manga", "placé"]
