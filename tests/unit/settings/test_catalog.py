"""shelfdrop.settings.catalog: the keys, kinds and bounds of the settings."""

import pytest

from shelfdrop.settings.catalog import (
    SECRETS,
    VALUES,
    invalid_keys,
    is_valid,
    sealed_names,
    torrent_secret,
)
from shelfdrop.settings.types import SettingValue


def test_the_catalog_holds_the_settings_of_the_page() -> None:
    assert {"prowlarr.url", "torrent.url", "jellyfin.url", "torrent.client"} <= set(VALUES)
    assert VALUES["search.max_names"].default == 6
    assert VALUES["search.release_cache_minutes"].default == 10
    assert VALUES["search.work_cache_hours"].default == 24
    assert VALUES["sources.mangadex.enabled"].default is True
    assert VALUES["discord.events.login"].default is True
    assert {
        "prowlarr.api_key",
        "torrent.api_key",
        "torrent.password",
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
        ("placement.scan_time", "04:30"),
        ("placement.scan_time", "23:59"),
        ("torrent.client", "qui"),
        ("torrent.client", "transmission"),
        ("torrent.username", "admin"),
        ("torrent.username", None),
        ("torrent.folder.manga", "/data/torrents/manga"),
        ("torrent.folder.manual", None),
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
        ("placement.scan_time", "24:00"),
        ("placement.scan_time", "4:30"),
        ("placement.scan_time", 430),
        ("torrent.client", "rtorrent"),
        ("torrent.client", None),
        ("torrent.username", ""),
        ("torrent.username", " admin"),
        ("torrent.username", "x" * 256),
        ("torrent.folder.manga", "torrents/manga"),
        # A library has a folder, always.
        ("placement.library.manga", None),
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


def test_qui_signs_in_with_its_key_and_the_other_clients_with_their_password() -> None:
    assert torrent_secret("qui") == "torrent.api_key"
    assert {torrent_secret(c) for c in ("qbittorrent", "deluge", "transmission")} == {
        "torrent.password"
    }


def test_the_key_of_qui_opens_under_the_name_it_had_before_the_torrent_clients() -> None:
    assert sealed_names("torrent.api_key") == ("torrent.api_key", "qbittorrent.api_key")
    assert sealed_names("prowlarr.api_key") == ("prowlarr.api_key",)
