"""SettingsService: the settings of the page and their secrets, read, changed with their audit,
and imported once from the environment."""

from collections.abc import Mapping
from typing import Final, Protocol

import anyio
import anyio.to_thread

from shelfdrop.settings.catalog import (
    ADDRESS,
    SECRETS,
    SERVICES,
    VALUES,
    invalid_keys,
    is_valid,
    sealed_names,
    torrent_secret,
)
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.exceptions import InvalidSettingsError, SecretUnreadableError
from shelfdrop.settings.monitor import ConnectionMonitor
from shelfdrop.settings.repository import SettingsRepository
from shelfdrop.settings.types import AuditRecord, ProbeResult, SettingsChange, SettingsView
from shelfdrop.works.types import Clock

# The keys already imported from the environment: each one is imported once (ADR 0012).
IMPORTED_KEY: Final = "settings.imported"
# The actor of the audit for a value imported from the environment.
ENVIRONMENT: Final = "environment"
AUDIT_SHOWN: Final = 100


class Probes(Protocol):
    def names(self) -> tuple[str, ...]: ...

    async def run(self, service: str, url: str | None, secret: str | None) -> ProbeResult: ...


def secret_key_of(service: str, client: str) -> str | None:
    """The key of the secret a test of `service` uses; `client`: the torrent client saved."""
    if service == "torrent":
        return torrent_secret(client)
    if service in SERVICES:
        return f"{service}.api_key"
    return "sources.myanimelist.client_id" if service == "myanimelist" else None


class SettingsService:
    def __init__(
        self,
        repository: SettingsRepository,
        box: SecretBox,
        clock: Clock,
        probes: Probes,
        monitor: ConnectionMonitor,
    ) -> None:
        self.repository = repository
        self.box = box
        self.clock = clock
        self.probes = probes
        self.monitor = monitor

    async def read(self) -> SettingsView:
        return await anyio.to_thread.run_sync(self.view)

    def view(self) -> SettingsView:
        saved = self.repository.read_values(VALUES)
        dates = self.repository.read_secret_dates()
        return SettingsView(
            values={key: saved.get(key, entry.default) for key, entry in VALUES.items()},
            secrets={key: dates.get(key) for key in sorted(SECRETS)},
        )

    async def save(self, change: SettingsChange, actor: str) -> SettingsView:
        """The values and the secrets given, the others unchanged; each change is audited,
        never its value. Raises InvalidSettingsError, and nothing is saved."""
        invalid = invalid_keys(change.values, change.secrets)
        if invalid:
            raise InvalidSettingsError(invalid)
        return await anyio.to_thread.run_sync(self.write, change, actor)

    def write(self, change: SettingsChange, actor: str) -> SettingsView:
        now = int(self.clock.now())
        before = self.view()
        for key, value in change.values.items():
            if before.values[key] != value:
                self.repository.save_value(key, value, now, actor)
                self.repository.add_audit(now, actor, "changed", key)
        for key, secret in change.secrets.items():
            if secret is not None:
                self.repository.save_sealed(key, self.box.seal(key, secret), now, actor)
                self.repository.add_audit(now, actor, "replaced", key)
            elif self.repository.remove_secret(key):
                self.repository.add_audit(now, actor, "cleared", key)
        self.repository.commit()
        return self.view()

    async def test(self, service: str, url: str | None, secret: str | None) -> ProbeResult:
        """The test of a connection with the values typed: `url` and `secret` None are those
        saved, a `secret` "" none. Raises InvalidSettingsError for an unknown service or an
        address refused."""
        if service not in self.probes.names():
            raise InvalidSettingsError([service])
        if url is not None and (service not in SERVICES or ADDRESS.match(url) is None):
            raise InvalidSettingsError([f"{service}.url"])
        saved_url, saved_secret = await anyio.to_thread.run_sync(self.saved_connection, service)
        return await self.probes.run(
            service,
            saved_url if url is None else url,
            saved_secret if secret is None else (secret or None),
        )

    def saved_connection(self, service: str) -> tuple[str | None, str | None]:
        client = self.repository.read_values(["torrent.client"]).get("torrent.client")
        url_key = f"{service}.url"
        default = str(VALUES["torrent.client"].default)
        secret_key = secret_key_of(service, client if isinstance(client, str) else default)
        url = self.repository.read_values([url_key]).get(url_key) if service in SERVICES else None
        sealed = None if secret_key is None else self.repository.read_sealed(secret_key)
        secret = None
        if secret_key is not None and sealed is not None:
            try:
                secret = self.box.open_any(sealed_names(secret_key), sealed)
            except SecretUnreadableError:
                secret = None
        return (url if isinstance(url, str) else None), secret

    def health(self) -> tuple[list[ProbeResult], int | None]:
        """The last background tests of the services saved."""
        return self.monitor.last()

    async def read_audit(self) -> list[AuditRecord]:
        return await anyio.to_thread.run_sync(self.repository.read_audit, AUDIT_SHOWN)

    async def import_environment(self, found: Mapping[str, str]) -> list[str]:
        """The values of the environment (`found`, by key of the catalog) the database does not
        hold yet, each imported once: a value cleared on the page later is not imported again.
        Returns the keys imported."""
        return await anyio.to_thread.run_sync(self.import_once, found)

    def import_once(self, found: Mapping[str, str]) -> list[str]:
        now = int(self.clock.now())
        done = self.repository.read_value(IMPORTED_KEY)
        seen = {str(key) for key in done} if isinstance(done, list) else set()
        saved = self.repository.read_values(VALUES)
        dates = self.repository.read_secret_dates()
        imported: list[str] = []
        for key, value in sorted(found.items()):
            if key in seen:
                continue
            if key in SECRETS and key not in dates and not invalid_keys({}, {key: value}):
                self.repository.save_sealed(key, self.box.seal(key, value), now, ENVIRONMENT)
            elif key in VALUES and key not in saved and is_valid(VALUES[key], value):
                self.repository.save_value(key, value, now, ENVIRONMENT)
            else:
                continue
            self.repository.add_audit(now, ENVIRONMENT, "imported", key)
            seen.add(key)
            imported.append(key)
        if imported:
            self.repository.save_value(IMPORTED_KEY, sorted(seen), now, ENVIRONMENT)
            self.repository.commit()
        return imported
