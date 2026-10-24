"""A settings reader on values in memory, for the services that read their settings at each
call."""

from collections.abc import Iterable, Mapping
from typing import Final, override

from shelfdrop.settings.catalog import VALUES
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.reader import SettingsReader
from shelfdrop.settings.repository import SettingsRepository
from shelfdrop.settings.types import AuditAction, AuditRecord, ProbeResult, SettingValue
from tests.unit.support import no_session

TEST_SECRET_KEY: Final = "k" * 32


class FakeSettingsReader(SettingsReader):
    """The real reader, its values and secrets in memory instead of the database."""

    def __init__(
        self,
        values: Mapping[str, SettingValue] | None = None,
        secrets: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(lambda: SettingsRepository(no_session()), SecretBox(TEST_SECRET_KEY))
        self.values = dict(values or {})
        self.secrets = dict(secrets or {})

    @override
    def read(
        self, keys: tuple[str, ...], secrets: tuple[str, ...]
    ) -> tuple[dict[str, SettingValue], dict[str, str | None]]:
        return (
            {key: self.values.get(key, VALUES[key].default) for key in keys},
            {key: self.secrets.get(key) for key in secrets},
        )


class FakeSettingsRepository(SettingsRepository):
    """The tables in memory; it counts the commits."""

    def __init__(self) -> None:
        super().__init__(no_session())
        self.values: dict[str, object] = {}
        self.sealed: dict[str, tuple[bytes, int, str]] = {}
        self.audit: list[AuditRecord] = []
        self.commits = 0

    @override
    def read_values(self, keys: Iterable[str]) -> dict[str, SettingValue]:
        wanted = set(keys)
        return {k: v for k, v in self.values.items() if k in wanted}  # type: ignore[misc]  # the fake keeps what the service saved, SettingValue for the catalog keys

    @override
    def read_value(self, key: str) -> object | None:
        return self.values.get(key)

    @override
    def save_value(self, key: str, value: object, now: int, actor: str) -> None:
        self.values[key] = value

    @override
    def read_secret_dates(self) -> dict[str, int]:
        return {key: at for key, (_, at, _) in self.sealed.items()}

    @override
    def read_sealed(self, key: str) -> bytes | None:
        found = self.sealed.get(key)
        return None if found is None else found[0]

    @override
    def save_sealed(self, key: str, sealed: bytes, now: int, actor: str) -> None:
        self.sealed[key] = (sealed, now, actor)

    @override
    def remove_secret(self, key: str) -> bool:
        return self.sealed.pop(key, None) is not None

    @override
    def add_audit(self, at: int, actor: str, action: AuditAction, target: str) -> None:
        self.audit.append(AuditRecord(at=at, actor=actor, action=action, target=target))

    @override
    def read_audit(self, limit: int) -> list[AuditRecord]:
        return list(reversed(self.audit))[:limit]

    @override
    def commit(self) -> None:
        self.commits += 1


class FakeProbes:
    """Every test answers `connected`, and keeps what it was given."""

    def __init__(self) -> None:
        self.runs: list[tuple[str, str | None, str | None]] = []

    def names(self) -> tuple[str, ...]:
        return ("prowlarr", "torrent", "jellyfin", "kitsu", "myanimelist")

    async def run(self, service: str, url: str | None, secret: str | None) -> ProbeResult:
        self.runs.append((service, url, secret))
        return ProbeResult(service=service, state="connected")
