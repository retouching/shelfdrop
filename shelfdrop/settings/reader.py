"""SettingsReader: the settings as the other domains read them at each use (a container
singleton). Each read opens a session of its own in the threadpool; a secret is opened in memory
alone, at the time of the call that needs it."""

import logging
from typing import Final

import anyio
import anyio.to_thread

from shelfdrop.settings.catalog import (
    CLIENTS,
    EVENTS,
    LIBRARIES,
    SOURCES,
    TORRENT_FOLDERS,
    VALUES,
    sealed_names,
    torrent_secret,
)
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.exceptions import SecretUnreadableError
from shelfdrop.settings.repository import SettingsRepositoryFactory
from shelfdrop.settings.types import SettingValue, TorrentSettings
from shelfdrop.works.types import Kind

logger = logging.getLogger(__name__)

MYANIMELIST_KEY: Final = "sources.myanimelist.client_id"
WEBHOOK_KEY: Final = "discord.webhook"


def secret_of(torrent: TorrentSettings) -> str | None:
    """The secret the torrent client chosen signs in with."""
    if torrent_secret(torrent.client) == "torrent.api_key":
        return torrent.api_key
    return torrent.password


class SettingsReader:
    def __init__(self, repositories: SettingsRepositoryFactory, box: SecretBox) -> None:
        self.repositories = repositories
        self.box = box

    def read(
        self, keys: tuple[str, ...], secrets: tuple[str, ...]
    ) -> tuple[dict[str, SettingValue], dict[str, str | None]]:
        """The values of `keys` (their default when never saved) and the secrets of `secrets`
        (None when unset or unreadable)."""
        repository = self.repositories()
        try:
            saved = repository.read_values(keys)
            sealed = {key: repository.read_sealed(key) for key in secrets}
        finally:
            repository.close()
        values = {key: saved.get(key, VALUES[key].default) for key in keys}
        return values, {key: self.opened(key, value) for key, value in sealed.items()}

    def opened(self, key: str, sealed: bytes | None) -> str | None:
        if sealed is None:
            return None
        try:
            return self.box.open_any(sealed_names(key), sealed)
        except SecretUnreadableError:
            logger.warning("Secret unreadable", extra={"setting": key})
            return None

    async def connection(self, service: str) -> tuple[str | None, str | None]:
        """The address and the secret of a service (`prowlarr`, `torrent`, `jellyfin`): its API
        key, or the secret the torrent client chosen signs in with."""
        if service == "torrent":
            torrent = await self.torrent()
            return torrent.url, secret_of(torrent)
        url_key, secret_key = f"{service}.url", f"{service}.api_key"
        values, secrets = await anyio.to_thread.run_sync(self.read, (url_key,), (secret_key,))
        url = values[url_key]
        return (url if isinstance(url, str) else None), secrets[secret_key]

    async def prowlarr(self) -> tuple[str | None, str | None]:
        return await self.connection("prowlarr")

    async def torrent(self) -> TorrentSettings:
        """The torrent client chosen, its address and how it signs in."""
        keys = ("torrent.client", "torrent.url", "torrent.username")
        secrets = ("torrent.password", "torrent.api_key")
        values, opened = await anyio.to_thread.run_sync(self.read, keys, secrets)
        client, url, username = (values[key] for key in keys)
        return TorrentSettings(
            client=client if isinstance(client, str) and client in CLIENTS else CLIENTS[0],
            url=url if isinstance(url, str) else None,
            username=username if isinstance(username, str) else None,
            password=opened["torrent.password"],
            api_key=opened["torrent.api_key"],
        )

    async def torrent_folders(self) -> dict[str, str]:
        """The folder of the torrent client of each kind of download (`manga`, `ebook`,
        `audiobook`, `manual`) that has one."""
        keys = tuple(f"torrent.folder.{name}" for name in TORRENT_FOLDERS)
        values, _ = await anyio.to_thread.run_sync(self.read, keys, ())
        return {
            name: value
            for name, key in zip(TORRENT_FOLDERS, keys, strict=True)
            if isinstance(value := values[key], str)
        }

    async def jellyfin_url(self) -> str | None:
        url, _ = await self.connection("jellyfin")
        return url

    async def myanimelist_client_id(self) -> str | None:
        _, secrets = await anyio.to_thread.run_sync(self.read, (), (MYANIMELIST_KEY,))
        return secrets[MYANIMELIST_KEY]

    async def enabled_sources(self) -> frozenset[str]:
        """The sources switched on; MyAnimeList only with its Client ID."""
        keys = tuple(f"sources.{source}.enabled" for source in SOURCES)
        values, secrets = await anyio.to_thread.run_sync(self.read, keys, (MYANIMELIST_KEY,))
        return frozenset(
            source
            for source, key in zip(SOURCES, keys, strict=True)
            if values[key] is True and (source != "myanimelist" or secrets[MYANIMELIST_KEY])
        )

    async def number(self, key: str) -> int:
        values, _ = await anyio.to_thread.run_sync(self.read, (key,), ())
        value = values[key]
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        default = VALUES[key].default
        return default if isinstance(default, int) else 0

    async def max_names(self) -> int:
        return await self.number("search.max_names")

    async def release_answer_seconds(self) -> int:
        return 60 * await self.number("search.release_cache_minutes")

    async def work_answer_seconds(self) -> int:
        return 3600 * await self.number("search.work_cache_hours")

    async def jellyfin(self) -> tuple[str | None, str | None]:
        """The address of Jellyfin and its API key."""
        return await self.connection("jellyfin")

    async def switch(self, key: str) -> bool:
        values, _ = await anyio.to_thread.run_sync(self.read, (key,), ())
        return values[key] is True

    async def libraries(self) -> dict[Kind, str]:
        """The folder of each library, as the container sees it."""
        keys = tuple(f"placement.library.{kind}" for kind in LIBRARIES)
        values, _ = await anyio.to_thread.run_sync(self.read, keys, ())
        return {
            kind: value if isinstance(value := values[key], str) else default
            for (kind, default), key in zip(LIBRARIES.items(), keys, strict=True)
        }

    async def waiting_seconds(self) -> int:
        """Seconds between two searches of a waiting search."""
        return 3600 * await self.number("waiting.interval_hours")

    async def merge_mp3(self) -> bool:
        return await self.switch("placement.merge_mp3")

    async def covers(self) -> bool:
        return await self.switch("placement.covers")

    async def lock_jellyfin(self) -> bool:
        return await self.switch("placement.lock_jellyfin")

    async def uploads_folder(self) -> str:
        """The folder of the files sent, as the placement worker sees it."""
        key = "uploads.folder"
        values, _ = await anyio.to_thread.run_sync(self.read, (key,), ())
        value = values[key]
        return value if isinstance(value, str) else "/data/envois"

    async def upload_keep_days(self) -> int:
        return await self.number("uploads.keep_days")

    async def scan_time(self) -> tuple[int, int]:
        """The hour and the minute of the day of the scan of the files misplaced."""
        key = "placement.scan_time"
        values, _ = await anyio.to_thread.run_sync(self.read, (key,), ())
        value = values[key]
        text = value if isinstance(value, str) else "04:30"
        hour, minute = text.split(":")
        return int(hour), int(minute)

    async def discord(self) -> tuple[str | None, frozenset[str]]:
        """The webhook of the journal and the events switched on."""
        keys = tuple(f"discord.events.{event}" for event in EVENTS)
        values, secrets = await anyio.to_thread.run_sync(self.read, keys, (WEBHOOK_KEY,))
        events = frozenset(
            event for event, key in zip(EVENTS, keys, strict=True) if values[key] is True
        )
        return secrets[WEBHOOK_KEY], events

    async def journal_language(self) -> str:
        """The language of the messages of the journal: `fr` or `en`."""
        key = "journal.language"
        values, _ = await anyio.to_thread.run_sync(self.read, (key,), ())
        value = values[key]
        return value if isinstance(value, str) else "fr"
