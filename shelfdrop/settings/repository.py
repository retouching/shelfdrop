"""SettingsRepository: the settings, the sealed secrets and the audit."""

import json
from collections.abc import Callable, Iterable
from typing import Final

from pydantic import TypeAdapter
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from shelfdrop.db.models import AuditEntry, Secret, Setting
from shelfdrop.settings.types import AuditAction, AuditRecord, SettingValue

ACTION: Final = TypeAdapter[AuditAction](AuditAction)


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read_values(self, keys: Iterable[str]) -> dict[str, SettingValue]:
        """The saved values of `keys`; a key never saved is missing."""
        rows = self.session.scalars(select(Setting).where(Setting.key.in_(list(keys))))
        return {row.key: json.loads(row.value) for row in rows}

    def read_value(self, key: str) -> object | None:
        row = self.session.get(Setting, key)
        return None if row is None else json.loads(row.value)

    def save_value(self, key: str, value: object, now: int, actor: str) -> None:
        self.session.merge(
            Setting(key=key, value=json.dumps(value), updated_at=now, updated_by=actor)
        )

    def read_secret_dates(self) -> dict[str, int]:
        """When each secret was set, by its key."""
        rows = self.session.execute(select(Secret.key, Secret.updated_at))
        return {key: updated_at for key, updated_at in rows.tuples()}

    def read_sealed(self, key: str) -> bytes | None:
        row = self.session.get(Secret, key)
        return None if row is None else row.ciphertext

    def save_sealed(self, key: str, sealed: bytes, now: int, actor: str) -> None:
        self.session.merge(Secret(key=key, ciphertext=sealed, updated_at=now, updated_by=actor))

    def remove_secret(self, key: str) -> bool:
        """Whether there was one."""
        row = self.session.get(Secret, key)
        if row is None:
            return False
        self.session.delete(row)
        return True

    def add_audit(self, at: int, actor: str, action: AuditAction, target: str) -> None:
        self.session.add(AuditEntry(at=at, actor=actor, action=action, target=target))

    def read_audit(self, limit: int) -> list[AuditRecord]:
        """The last entries, the newest first."""
        rows = self.session.scalars(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit))
        return [
            AuditRecord(
                at=row.at,
                actor=row.actor,
                action=ACTION.validate_python(row.action),
                target=row.target,
            )
            for row in rows
        ]

    def commit(self) -> None:
        self.session.commit()

    def close(self) -> None:
        self.session.close()


type SettingsRepositoryFactory = Callable[[], SettingsRepository]


def settings_repository_factory(engine: Engine) -> SettingsRepositoryFactory:
    """New repositories on their own session, for the reads outside a request (the settings
    read at each call of a service); the caller closes each."""

    def new() -> SettingsRepository:
        return SettingsRepository(Session(engine, expire_on_commit=False))

    return new
