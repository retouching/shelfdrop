"""The connector of Deluge against a real Deluge (the service `deluge` of the test stack, its Web
UI on the network of the fake sources, with no way out, the torrents in the volume of the
placement worker): the test of the connection through the settings, the labels missing then
made, the refusal without the plugin Label (nothing sent), and a release sent, labelled,
checked complete on its files, placed by the worker, never tagged (Deluge has no tags).

Deluge is driven from the container of the API (`deluge_calls`): its Web UI is not published."""

import base64
import hashlib
import io
import json
import zipfile
from collections.abc import Iterator
from typing import Any, Final

import httpx
import pytest

from shelfdrop.utils.torrent import torrent_id
from tests.integration.support import (
    FakeSources,
    Stack,
    prowlarr_download_stub,
    prowlarr_release,
    prowlarr_search_stub,
    run_search,
    wait_for_download,
)
from tests.unit.support import Bencodable, bencode

pytestmark = [pytest.mark.torrents, pytest.mark.torrent_deluge]

DELUGE_URL: Final = "http://deluge:8112"
# The password of the Web UI of the image, as it starts.
DELUGE_PASSWORD: Final = "deluge"
CATEGORIES: Final = ["manga", "ebook", "audiobook", "shelfdrop-manual"]
# Run in the container of the API: signs in, connects the Web UI to its daemon, then makes the
# calls of argv[1] (`[[method, params], ...]`) and prints their answers (`result`, `error`).
DELUGE_CALLS: Final = """
import http.cookiejar, json, sys, urllib.request
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(method, params):
    body = json.dumps({"method": method, "params": params, "id": 1}).encode()
    request = urllib.request.Request(
        "@URL@/json", data=body, headers={"Content-Type": "application/json"}
    )
    with opener.open(request, timeout=10) as response:
        return json.loads(response.read())
assert call("auth.login", ["@PASSWORD@"])["result"] is True
if not call("web.connected", [])["result"]:
    call("web.connect", [call("web.get_hosts", [])["result"][0][0]])
print(json.dumps([call(method, params) for method, params in json.loads(sys.argv[1])]))
""".replace("@URL@", DELUGE_URL).replace("@PASSWORD@", DELUGE_PASSWORD)


def deluge_calls(stack: Stack, *calls: tuple[str, list[Any]]) -> list[dict[str, Any]]:
    """The answers of the Web UI of Deluge to `calls`, made in order."""
    result = stack.exec_api("python", "-c", DELUGE_CALLS, json.dumps(calls))
    assert result.returncode == 0, result.stderr
    answers: list[dict[str, Any]] = json.loads(result.stdout)
    return answers


def label_plugin(stack: Stack, *, on: bool) -> None:
    deluge_calls(stack, ("core.enable_plugin" if on else "core.disable_plugin", ["Label"]))


def probe(client: httpx.Client) -> dict[str, Any]:
    body = {"service": "torrent", "url": DELUGE_URL, "secret": DELUGE_PASSWORD}
    response = client.post("/api/v1/settings/test", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


@pytest.fixture
def deluge_saved(client: httpx.Client, stack: Stack) -> Iterator[None]:
    """Deluge saved as the torrent client, its plugin Label on, the manga downloaded into
    /data/torrents/manga; then qui again, cleared."""
    label_plugin(stack, on=True)
    saved = {
        "values": {
            "torrent.client": "deluge",
            "torrent.url": DELUGE_URL,
            "torrent.folder.manga": "/data/torrents/manga",
        },
        "secrets": {"torrent.password": DELUGE_PASSWORD},
    }
    client.put("/api/v1/settings", json=saved).raise_for_status()
    yield
    label_plugin(stack, on=True)
    cleared = {
        "values": {"torrent.client": "qui", "torrent.url": None, "torrent.folder.manga": None},
        "secrets": {"torrent.password": None},
    }
    client.put("/api/v1/settings", json=cleared).raise_for_status()


def cbz(name: str) -> bytes:
    """A small `.cbz` of one page."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("001.jpg", b"\xff\xd8\xff\xe0" + name.encode())
    return buffer.getvalue()


def real_torrent(name: str, data: bytes) -> tuple[bytes, str]:
    """A `.torrent` of the one file `name` holding `data`, with its true pieces (Deluge checks
    them against the file), no tracker; and its info hash."""
    length = 16384
    pieces = b"".join(
        hashlib.sha1(data[i : i + length], usedforsecurity=False).digest()
        for i in range(0, len(data), length)
    )
    info: dict[str, Bencodable] = {
        "name": name,
        "length": len(data),
        "piece length": length,
        "pieces": pieces,
    }
    torrent = bencode({"info": info})
    digest = torrent_id(torrent)
    assert digest is not None
    return torrent, digest


def send(client: httpx.Client, fake_sources: FakeSources, series: str, torrent: bytes) -> int:
    """The release of `series` (its volume 1) searched in the fake Prowlarr and sent: the id of
    its download."""
    link = series.lower().replace(" ", "-")
    fake_sources.load(
        [
            prowlarr_search_stub(
                series,
                [7030],
                [
                    prowlarr_release(
                        f"https://nyaa.test/view/{link}",
                        f"{series.replace(' ', '.')}.T01.FRENCH.CBZ",
                        link,
                    )
                ],
            ),
            prowlarr_download_stub(1, link, torrent),
        ]
    )
    search = run_search(
        client, {"mode": "work", "kind": "manga", "title": series, "names": [series]}
    )
    sent = client.post(
        "/api/v1/downloads",
        json={
            "search_id": search["progress"]["id"],
            "series": series,
            "releases": [
                {"id": search["releases"][0]["id"], "volumes": {"kind": "single", "first": 1}}
            ],
        },
    )
    assert sent.status_code == 200, sent.text
    download_id: int = sent.json()["downloads"][0]["id"]
    return download_id


@pytest.mark.usefixtures("deluge_saved")
def test_the_connection_names_the_labels_missing_then_finds_them(
    client: httpx.Client, stack: Stack
) -> None:
    deluge_calls(stack, *(("label.remove", [label]) for label in CATEGORIES))

    missing = probe(client)
    deluge_calls(stack, *(("label.add", [label]) for label in CATEGORIES))
    found = probe(client)

    assert (missing["ok"], missing["state"], missing["version"]) == (True, "connected", "2.2.0")
    assert missing["count"] == 0
    assert missing["missing"] == CATEGORIES
    assert (found["ok"], found["count"], found["missing"]) == (True, 4, [])
    wrong = client.post(
        "/api/v1/settings/test",
        json={"service": "torrent", "url": DELUGE_URL, "secret": "wrong"},
    ).json()
    assert (wrong["state"], wrong["status"]) == ("refused", 401)


@pytest.mark.usefixtures("deluge_saved")
def test_without_the_plugin_label_the_connection_is_unavailable_and_nothing_is_sent(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Deluge Refused"
    torrent, digest = real_torrent(f"{series} T01.cbz", cbz(series))
    label_plugin(stack, on=False)

    result = probe(client)
    download_id = send(client, fake_sources, series, torrent)
    failed = wait_for_download(client, download_id, lambda d: d["progress"]["state"] != "waiting")

    assert (result["ok"], result["state"], result["version"]) == (False, "unavailable", "2.2.0")
    assert (failed["progress"]["state"], failed["progress"]["reason"]) == ("failed", "not_received")
    [listed] = deluge_calls(stack, ("core.get_torrents_status", [{"id": [digest]}, ["name"]]))
    assert listed["result"] == {}


@pytest.mark.usefixtures("media", "deluge_saved")
def test_a_release_sent_is_labelled_complete_on_its_files_placed_and_never_tagged(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Deluge Test"
    name = f"{series} T01.cbz"
    data = cbz(series)
    torrent, digest = real_torrent(name, data)
    deluge_calls(stack, ("label.remove", ["manga"]))
    # The file is there before the add: Deluge checks it, complete, with no peer.
    stack.exec_placement(
        "python",
        "-c",
        "import base64, pathlib, sys; p = pathlib.Path(sys.argv[1]);"
        " p.parent.mkdir(parents=True, exist_ok=True);"
        " p.write_bytes(base64.b64decode(sys.argv[2]))",
        f"/data/torrents/manga/{name}",
        base64.b64encode(data).decode(),
    )

    download_id = send(client, fake_sources, series, torrent)
    placed = wait_for_download(
        client, download_id, lambda d: d["progress"]["state"] in ("placed", "to_place", "failed")
    )

    assert placed["progress"]["state"] == "placed", placed
    [status, labels] = deluge_calls(
        stack,
        ("core.get_torrents_status", [{"id": [digest]}, ["state", "label", "save_path", "name"]]),
        ("label.get_labels", []),
    )
    assert status["result"] == {
        digest: {
            "state": "Seeding",
            "label": "manga",
            "save_path": "/data/torrents/manga",
            "name": name,
        }
    }
    # The label removed was made again by the send.
    assert "manga" in labels["result"]
    shelf = stack.exec_placement("ls", "-1", f"/data/files/comics/{series}")
    assert f"{series} - T01.cbz" in shelf.stdout.splitlines()
