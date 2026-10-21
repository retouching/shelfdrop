"""Types of the settings: one setting of the page, the settings as the page reads them, a change,
and an entry of the audit."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

type ValueKind = Literal["address", "number", "switch"]
type SettingValue = str | int | bool | None
type AuditAction = Literal["changed", "replaced", "cleared", "imported"]


@dataclass(frozen=True, kw_only=True)
class Entry:
    """A setting of the page: an address (None when unset), a whole number within its bounds,
    or a switch."""

    kind: ValueKind
    default: SettingValue
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True, kw_only=True)
class SettingsView:
    values: Mapping[str, SettingValue]
    """Every setting of the catalog, the default of those never saved."""
    secrets: Mapping[str, int | None]
    """Every secret of the catalog: when it was set (Unix seconds), None when it is not."""


@dataclass(frozen=True, kw_only=True)
class SettingsChange:
    values: Mapping[str, SettingValue]
    secrets: Mapping[str, str | None]
    """A new value, or None to clear the secret."""


@dataclass(frozen=True, kw_only=True)
class AuditRecord:
    at: int
    actor: str
    action: AuditAction
    target: str
