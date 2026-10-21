"""SettingsReader: the settings as the other domains read them at each use (a container
singleton). Each read opens a session of its own in the threadpool; a secret is opened in memory
alone, at the time of the call that needs it."""

import logging
from typing import Final

import anyio
import anyio.to_thread

from shelfdrop.settings.catalog import SOURCES, VALUES
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.exceptions import SecretUnreadableError
from shelfdrop.settings.repository import SettingsRepositoryFactory
from shelfdrop.settings.types import SettingValue

logger = logging.getLogger(__name__)

MYANIMELIST_KEY: Final = "sources.myanimelist.client_id"


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
            return self.box.open(key, sealed)
        except SecretUnreadableError:
            logger.warning("Secret unreadable", extra={"setting": key})
            return None

    async def connection(self, service: str) -> tuple[str | None, str | None]:
        """The address and the API key of a service (`prowlarr`, `qbittorrent`, `jellyfin`)."""
        url_key, secret_key = f"{service}.url", f"{service}.api_key"
        values, secrets = await anyio.to_thread.run_sync(self.read, (url_key,), (secret_key,))
        url = values[url_key]
        return (url if isinstance(url, str) else None), secrets[secret_key]

    async def prowlarr(self) -> tuple[str | None, str | None]:
        return await self.connection("prowlarr")

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
