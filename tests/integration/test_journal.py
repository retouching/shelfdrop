"""The journal through the real API (plan section 3, point 7): the events posted on the webhook
of Discord as embeds, one message for the volumes sent by one request, the color of each type,
a type switched off, a failure. The webhook is played by the fake sources."""

from typing import Any

import httpx
import pytest

from shelfdrop.utils.torrent import torrent_id
from tests.integration.support import (
    FakeSources,
    prowlarr_download_stub,
    prowlarr_release,
    prowlarr_search_stub,
    run_search,
    torrent_stubs,
    wait_for_download,
    wait_for_messages,
)
from tests.unit.support import torrent_file

pytestmark = [pytest.mark.journal]


def send_volumes(
    client: httpx.Client, fake_sources: FakeSources, name: str, volumes: list[int]
) -> list[dict[str, Any]]:
    """The volumes `volumes` of the work `name`, one release each, sent by one request."""
    releases = []
    for n in volumes:
        data = torrent_file(f"{name} T{n:02d}")
        digest = torrent_id(data)
        assert digest is not None
        link = f"{name.lower().replace(' ', '-')}-{n}"
        fake_sources.load(
            [prowlarr_download_stub(1, link, data), *torrent_stubs(digest, f"{name} T{n:02d}")]
        )
        releases.append(
            prowlarr_release(
                f"https://nyaa.test/view/{link}",
                f"{name.replace(' ', '.')}.T{n:02d}.FRENCH.CBZ",
                link,
            )
        )
    fake_sources.load([prowlarr_search_stub(name, [7030], releases)])
    search = run_search(client, {"mode": "work", "kind": "manga", "title": name, "names": [name]})
    found = {r["volumes"]["first"]: r["id"] for r in search["releases"]}
    sent = client.post(
        "/api/v1/downloads",
        json={
            "search_id": search["progress"]["id"],
            "work_id": None,
            "author": "Tatsuki Fujimoto",
            "series": name,
            "releases": [
                {"id": found[n], "volumes": {"kind": "single", "first": n, "last": n}}
                for n in volumes
            ],
        },
    )
    assert sent.status_code == 200, sent.text
    downloads: list[dict[str, Any]] = sent.json()["downloads"]
    return downloads


@pytest.mark.usefixtures("qbittorrent_saved", "webhook_saved")
def test_the_volumes_sent_by_one_request_make_one_embed(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    downloads = send_volumes(client, fake_sources, "Shelfdrop Journal Test", [1, 2, 3])
    for download in downloads:
        wait_for_download(client, download["id"], lambda d: d["progress"]["state"] != "waiting")

    messages = wait_for_messages(fake_sources, "Shelfdrop Journal Test")

    assert len(messages) == 1
    [embed] = messages[0]["embeds"]
    assert embed["title"] == "Envoyé : Shelfdrop Journal Test"
    assert embed["color"] == 0x6E56CF
    assert embed["url"] == "http://shelfdrop.test"
    assert embed["footer"] == {"text": "shelfdrop"}
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Tomes"] == "T01 à T03"
    assert fields["Mode"] == "Automatique"
    assert fields["Par"] == "admin"
    assert "apikey" not in str(messages)


@pytest.mark.usefixtures("qbittorrent_saved", "webhook_saved")
def test_a_type_switched_off_is_not_posted_and_a_failure_is(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    client.put(
        "/api/v1/settings", json={"values": {"discord.events.sent": False}}
    ).raise_for_status()
    try:
        downloads = send_volumes(client, fake_sources, "Shelfdrop Journal Off", [1])
        wait_for_download(client, downloads[0]["id"], lambda d: d["progress"]["state"] != "waiting")
        # A release whose torrent Prowlarr does not give: not received.
        fake_sources.load(
            [
                prowlarr_search_stub(
                    "Shelfdrop Journal Lost",
                    [7030],
                    [
                        prowlarr_release(
                            "https://nyaa.test/view/lost",
                            "Shelfdrop.Journal.Lost.T01.FRENCH.CBZ",
                            "journal-lost",
                        )
                    ],
                )
            ]
        )
        search = run_search(
            client,
            {
                "mode": "work",
                "kind": "manga",
                "title": "Shelfdrop Journal Lost",
                "names": ["Shelfdrop Journal Lost"],
            },
        )
        lost = client.post(
            "/api/v1/downloads",
            json={
                "search_id": search["progress"]["id"],
                "releases": [{"id": search["releases"][0]["id"], "volumes": {"kind": "unknown"}}],
            },
        )
        assert lost.status_code == 200, lost.text

        failed = wait_for_messages(fake_sources, "Shelfdrop.Journal.Lost.T01")

        [embed] = failed[0]["embeds"]
        assert embed["title"] == "Échec : qBittorrent n'a pas reçu le torrent"
        assert embed["color"] == 0xE5484D
        assert wait_for_messages(fake_sources, "Shelfdrop Journal Off", seconds=3) == []
    finally:
        client.put(
            "/api/v1/settings", json={"values": {"discord.events.sent": True}}
        ).raise_for_status()
