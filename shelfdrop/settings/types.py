"""Types of the settings: one setting of the page, the settings as the page reads them, a change,
and an entry of the audit."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

type ValueKind = Literal["address", "number", "switch", "path", "time"]
type SettingValue = str | int | bool | None
type AuditAction = Literal["changed", "replaced", "cleared", "imported"]
type ProbeState = Literal["connected", "no_address", "no_key", "refused", "unavailable"]


@dataclass(frozen=True, kw_only=True)
class Entry:
    """A setting of the page: an address (None when unset), a whole number within its bounds
    (one of `choices` when set), a switch, an absolute path of the container, or a time of the
    day (`HH:MM`)."""

    kind: ValueKind
    default: SettingValue
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[int, ...] | None = None


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


@dataclass(frozen=True, kw_only=True)
class ProbeResult:
    """What a test of a connection found: `connected`, or why not."""

    service: str
    state: ProbeState
    status: int | None = None
    """The HTTP status of a refusal or of an error."""
    version: str | None = None
    count: int | None = None
    """Prowlarr: the indexers on; qBittorrent: the categories of shelfdrop found; Jellyfin: the
    libraries of books."""
    missing: tuple[str, ...] = ()
    """qBittorrent: the categories of shelfdrop it does not have."""
    elapsed_ms: int | None = None
    """A metadata source: the time of its answer."""

    @property
    def ok(self) -> bool:
        return self.state == "connected"
