"""The tests of the connections through the real API, against the fake
Prowlarr, qBittorrent (behind qui), Jellyfin and metadata sources: with the values typed before
they are saved, or those saved; and the tests of the background, run at start."""

from typing import Any

import httpx
import pytest

from tests.integration.support import FAKE_ORIGIN, JELLYFIN_API_KEY, QUI_KEY

pytestmark = [pytest.mark.settings, pytest.mark.settings_tests]


def probe(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/v1/settings/test", json=body)
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_prowlarr_saved_answers_with_its_version_and_its_indexers(client: httpx.Client) -> None:
    result = probe(client, {"service": "prowlarr"})

    assert result["ok"] is True
    assert result["state"] == "connected"
    assert result["version"] == "2.1.5.5216"
    assert result["count"] == 4


def test_a_key_typed_is_tested_before_it_is_saved(client: httpx.Client) -> None:
    result = probe(client, {"service": "prowlarr", "secret": "a-wrong-key"})

    assert result == {
        "service": "prowlarr",
        "ok": False,
        "state": "refused",
        "status": 401,
        "version": None,
        "count": None,
        "missing": [],
        "elapsed_ms": None,
    }
    assert client.get("/api/v1/settings").json()["secrets"]["prowlarr.api_key"] is not None


def test_qbittorrent_through_qui_names_the_category_it_misses(client: httpx.Client) -> None:
    result = probe(client, {"service": "qbittorrent", "url": FAKE_ORIGIN, "secret": QUI_KEY})

    assert result["ok"] is True
    assert result["version"] == "5.1.2"
    assert result["count"] == 3
    assert result["missing"] == ["shelfdrop-manual"]


def test_jellyfin_gives_its_version_and_its_libraries_of_books(client: httpx.Client) -> None:
    ok = probe(client, {"service": "jellyfin", "secret": JELLYFIN_API_KEY})
    without = probe(client, {"service": "jellyfin"})

    assert (ok["ok"], ok["version"], ok["count"]) == (True, "10.11.2", 3)
    assert without["state"] == "no_key"


def test_a_source_answers_its_fixed_search_or_is_named_unavailable(client: httpx.Client) -> None:
    kitsu = probe(client, {"service": "kitsu"})
    anilist = probe(client, {"service": "anilist"})

    assert kitsu["ok"] is True
    assert isinstance(kitsu["elapsed_ms"], int)
    assert anilist["state"] == "unavailable"


def test_an_unknown_service_or_a_bad_address_is_refused(client: httpx.Client) -> None:
    unknown = client.post("/api/v1/settings/test", json={"service": "sonarr"})
    address = client.post("/api/v1/settings/test", json={"service": "jellyfin", "url": "x:1"})

    assert unknown.json()["data"] == {"keys": ["sonarr"]}
    assert address.json()["data"] == {"keys": ["jellyfin.url"]}


def test_the_services_saved_were_tested_at_start(client: httpx.Client) -> None:
    """At start, Prowlarr alone has an address and a key (imported); its result depends on
    whether the stubs were loaded yet, which the start of the stack does not wait for."""
    health = client.get("/api/v1/settings/health").json()

    assert isinstance(health["checked_at"], int)
    assert [s["service"] for s in health["services"]] == ["prowlarr"]
    assert health["services"][0]["state"] in ("connected", "unavailable")
