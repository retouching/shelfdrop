"""shelfdrop.settings.catalog: the keys, kinds and bounds of the settings."""

import pytest

from shelfdrop.settings.catalog import SECRETS, VALUES, invalid_keys, is_valid
from shelfdrop.settings.types import SettingValue


def test_the_catalog_holds_the_settings_of_the_page() -> None:
    assert {"prowlarr.url", "qbittorrent.url", "jellyfin.url"} <= set(VALUES)
    assert VALUES["search.max_names"].default == 6
    assert VALUES["search.release_cache_minutes"].default == 10
    assert VALUES["search.work_cache_hours"].default == 24
    assert VALUES["sources.mangadex.enabled"].default is True
    assert VALUES["discord.events.login"].default is True
    assert {
        "prowlarr.api_key",
        "qbittorrent.api_key",
        "jellyfin.api_key",
        "sources.myanimelist.client_id",
        "discord.webhook",
    } == SECRETS
    assert not set(VALUES) & SECRETS


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("prowlarr.url", "http://prowlarr:9696"),
        ("prowlarr.url", "https://nami.lan/prowlarr"),
        ("prowlarr.url", None),
        ("search.max_names", 1),
        ("search.max_names", 10),
        ("search.release_cache_minutes", 0),
        ("sources.kitsu.enabled", False),
    ],
)
def test_a_valid_value_is_accepted(key: str, value: SettingValue) -> None:
    assert invalid_keys({key: value}, {}) == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("prowlarr.url", "ftp://prowlarr"),
        ("prowlarr.url", "prowlarr:9696"),
        ("prowlarr.url", "http://pro wlarr"),
        ("prowlarr.url", 3),
        ("search.max_names", 0),
        ("search.max_names", 11),
        ("search.max_names", True),
        ("search.max_names", "6"),
        ("sources.kitsu.enabled", 1),
        ("unknown.key", 1),
        ("prowlarr.api_key", "abc"),
    ],
)
def test_an_invalid_value_or_an_unknown_key_is_refused(key: str, value: SettingValue) -> None:
    assert invalid_keys({key: value}, {}) == [key]


@pytest.mark.parametrize("secret", ["", "a b", "a\nb", "x" * 1001])
def test_an_invalid_secret_is_refused(secret: str) -> None:
    assert invalid_keys({}, {"prowlarr.api_key": secret}) == ["prowlarr.api_key"]


def test_a_secret_is_cleared_with_none_and_an_unknown_one_refused() -> None:
    assert invalid_keys({}, {"prowlarr.api_key": None}) == []
    assert invalid_keys({}, {"prowlarr.url": "x"}) == ["prowlarr.url"]


def test_a_library_is_an_absolute_path_of_the_container() -> None:
    entry = VALUES["placement.library.manga"]

    assert is_valid(entry, "/data/files/comics")
    assert not is_valid(entry, "data/files/comics")
    assert not is_valid(entry, "/data/../etc")
    assert not is_valid(entry, "/data/files/")
    assert not is_valid(entry, 3)
