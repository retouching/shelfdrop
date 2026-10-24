"""The settings through the real API: kept in the database, a secret never
given back, each change audited without its value, the environment imported once, and each
change read by the next search, without a restart. Each test puts back what it changed."""

from collections.abc import Iterator
from typing import Any, Final

import httpx
import pytest

from tests.integration.support import FakeSources, json_response

pytestmark = [pytest.mark.settings, pytest.mark.settings_store]

MYANIMELIST: Final = "https://api.myanimelist.net"
KITSU: Final = "https://kitsu.io"
CLIENT_ID: Final = "mal-client-id-of-the-tests-41"


def save(client: httpx.Client, body: dict[str, Any]) -> httpx.Response:
    return client.put("/api/v1/settings", json=body)


@pytest.fixture
def restore(client: httpx.Client) -> Iterator[None]:
    """The settings as they were before the test."""
    before = client.get("/api/v1/settings").json()
    yield
    save(client, {"values": before["values"]}).raise_for_status()
    cleared = {key: None for key, at in before["secrets"].items() if at is None}
    save(client, {"secrets": cleared}).raise_for_status()


def test_the_environment_was_imported_once_and_no_secret_is_given_back(
    client: httpx.Client,
) -> None:
    body = client.get("/api/v1/settings")

    assert body.status_code == 200
    settings = body.json()
    assert settings["values"]["prowlarr.url"] == "http://fake-sources:8080"
    assert settings["values"]["jellyfin.url"] == "http://fake-sources:8080"
    assert settings["values"]["search.max_names"] == 6
    assert isinstance(settings["secrets"]["prowlarr.api_key"], int)
    assert settings["secrets"]["qbittorrent.api_key"] is None
    assert "test-prowlarr-key" not in body.text
    audit = client.get("/api/v1/settings/audit").json()["entries"]
    imported = {(e["actor"], e["target"]) for e in audit if e["action"] == "imported"}
    assert ("environment", "prowlarr.api_key") in imported


def test_a_change_is_kept_and_audited_without_its_value(
    client: httpx.Client, restore: None
) -> None:
    saved = save(
        client,
        {
            "values": {"qbittorrent.url": "http://qui:7476", "search.max_names": 4},
            "secrets": {"qbittorrent.api_key": "a-secret-of-the-tests-9e"},
        },
    )

    assert saved.status_code == 200
    body = saved.json()
    assert body["values"]["qbittorrent.url"] == "http://qui:7476"
    assert body["values"]["search.max_names"] == 4
    assert isinstance(body["secrets"]["qbittorrent.api_key"], int)
    assert "a-secret-of-the-tests-9e" not in saved.text
    audit = client.get("/api/v1/settings/audit")
    assert "a-secret-of-the-tests-9e" not in audit.text
    recent = [(e["actor"], e["action"], e["target"]) for e in audit.json()["entries"][:3]]
    assert set(recent) == {
        ("admin", "changed", "qbittorrent.url"),
        ("admin", "changed", "search.max_names"),
        ("admin", "replaced", "qbittorrent.api_key"),
    }


def test_the_number_of_names_saved_applies_to_the_next_search(
    client: httpx.Client, restore: None
) -> None:
    save(client, {"values": {"search.max_names": 2}}).raise_for_status()

    refused = client.post(
        "/api/v1/searches",
        json={"mode": "work", "kind": "manga", "title": "x", "names": ["Aa a", "Bb b", "Cc c"]},
    )

    assert refused.status_code == 422
    assert refused.json()["code"] == "too_many_names"


def test_an_invalid_setting_is_refused_by_its_key_alone(client: httpx.Client) -> None:
    refused = save(
        client,
        {
            "values": {"prowlarr.url": "not-an-address-77", "search.max_names": 99},
            "secrets": {"unknown.secret": "value-of-the-tests-88"},
        },
    )

    assert refused.status_code == 422
    assert refused.json() == {
        "code": "invalid_settings",
        "detail": "Invalid settings",
        "data": {"keys": ["prowlarr.url", "search.max_names", "unknown.secret"]},
    }
    assert "not-an-address-77" not in refused.text
    assert "value-of-the-tests-88" not in refused.text
    assert client.get("/api/v1/settings").json()["values"]["prowlarr.url"].startswith("http")


def test_myanimelist_is_asked_once_its_client_id_is_saved_without_a_restart(
    client: httpx.Client, fake_sources: FakeSources, restore: None
) -> None:
    text = "client id of the page 3c9a"
    fake_sources.load(
        [
            {
                "priority": 1,
                "request": {
                    "method": "GET",
                    "urlPath": "/v2/manga",
                    "headers": {
                        "X-Original-Origin": {"equalTo": MYANIMELIST},
                        "X-MAL-CLIENT-ID": {"equalTo": CLIENT_ID},
                    },
                },
                "response": json_response({"data": []}),
            }
        ]
    )
    client.get("/api/v1/works", params={"q": text, "kind": "manga"})
    assert fake_sources.count(MYANIMELIST, "/v2/manga") == 0

    save(client, {"secrets": {"sources.myanimelist.client_id": CLIENT_ID}}).raise_for_status()
    found = client.get("/api/v1/works", params={"q": f"{text} again", "kind": "manga"})

    assert found.status_code == 200
    assert "myanimelist" not in found.json()["unavailable"]
    assert fake_sources.count(MYANIMELIST, "/v2/manga") == 1


def test_a_source_switched_off_is_not_asked(
    client: httpx.Client, fake_sources: FakeSources, restore: None
) -> None:
    save(client, {"values": {"sources.kitsu.enabled": False}}).raise_for_status()
    before = fake_sources.count(KITSU, "/api/edge/manga")

    client.get("/api/v1/works", params={"q": "source switched off 5d0b", "kind": "manga"})

    assert fake_sources.count(KITSU, "/api/edge/manga") == before
