"""shelfdrop.settings.reader: the settings as the other domains read them."""

import pytest

from tests.unit.settings.support import FakeSettingsReader


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_defaults_hold_until_a_value_is_saved() -> None:
    reader = FakeSettingsReader()

    assert await reader.max_names() == 6
    assert await reader.release_answer_seconds() == 600
    assert await reader.work_answer_seconds() == 86400
    assert await reader.prowlarr() == (None, None)
    assert await reader.qbittorrent() == (None, None)


@pytest.mark.anyio
async def test_the_values_saved_are_read() -> None:
    reader = FakeSettingsReader(
        {
            "search.max_names": 3,
            "search.work_cache_hours": 2,
            "prowlarr.url": "http://p:9696",
            "qbittorrent.url": "http://qui:7476",
        },
        {"prowlarr.api_key": "key", "qbittorrent.api_key": "client-key"},
    )

    assert await reader.max_names() == 3
    assert await reader.work_answer_seconds() == 7200
    assert await reader.prowlarr() == ("http://p:9696", "key")
    assert await reader.qbittorrent() == ("http://qui:7476", "client-key")


@pytest.mark.anyio
async def test_myanimelist_is_asked_with_its_client_id_alone() -> None:
    without = await FakeSettingsReader().enabled_sources()
    with_id = await FakeSettingsReader(
        secrets={"sources.myanimelist.client_id": "abc"}
    ).enabled_sources()

    assert "myanimelist" not in without
    assert "myanimelist" in with_id
    assert "kitsu" in without


@pytest.mark.anyio
async def test_a_source_switched_off_is_not_asked() -> None:
    reader = FakeSettingsReader({"sources.anilist.enabled": False})

    assert "anilist" not in await reader.enabled_sources()


def test_a_secret_sealed_under_another_key_reads_as_unset() -> None:
    reader = FakeSettingsReader()
    sealed = reader.box.seal("jellyfin.api_key", "abc")

    assert reader.opened("prowlarr.api_key", sealed) is None
    assert reader.opened("jellyfin.api_key", sealed) == "abc"


@pytest.mark.anyio
async def test_the_placement_reads_its_libraries_and_its_switches() -> None:
    reader = FakeSettingsReader(
        {"placement.library.manga": "/data/media/comics", "placement.merge_mp3": False},
        {"discord.webhook": "https://discord.test/api/webhooks/1/t"},
    )

    assert await reader.libraries() == {
        "manga": "/data/media/comics",
        "ebook": "/data/files/ebooks",
        "audiobook": "/data/files/audiobooks",
    }
    assert await reader.merge_mp3() is False
    assert await reader.covers() is True
    assert await reader.lock_jellyfin() is True
    webhook, events = await reader.discord()
    assert webhook == "https://discord.test/api/webhooks/1/t"
    assert "found" in events
