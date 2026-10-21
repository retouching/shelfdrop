"""SettingsService: the settings of the page and their secrets, read, changed with their audit,
and imported once from the environment."""

from collections.abc import Mapping
from typing import Final

import anyio
import anyio.to_thread

from shelfdrop.settings.catalog import SECRETS, VALUES, invalid_keys, is_valid
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.exceptions import InvalidSettingsError
from shelfdrop.settings.repository import SettingsRepository
from shelfdrop.settings.types import AuditRecord, SettingsChange, SettingsView
from shelfdrop.works.types import Clock

# The keys already imported from the environment: each one is imported once (ADR 0012).
IMPORTED_KEY: Final = "settings.imported"
# The actor of the audit for a value imported from the environment.
ENVIRONMENT: Final = "environment"
AUDIT_SHOWN: Final = 100


class SettingsService:
    def __init__(self, repository: SettingsRepository, box: SecretBox, clock: Clock) -> None:
        self.repository = repository
        self.box = box
        self.clock = clock

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
