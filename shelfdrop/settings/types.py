"""Types of the settings: one setting of the page, the settings as the page reads them, a change,
and an entry of the audit."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

type ValueKind = Literal["address", "number", "switch", "path", "time", "choice", "text", "order"]
type SettingValue = str | int | bool | list[str] | None
type AuditAction = Literal["changed", "replaced", "cleared", "imported", "created", "revoked"]
type ProbeState = Literal[
    "connected", "no_address", "no_key", "refused", "unavailable", "unsupported", "no_connector"
]


@dataclass(frozen=True, kw_only=True)
class Entry:
    """A setting of the page: an address (None when unset), a whole number within its bounds
    (one of `choices` when set), a switch, an absolute path of the container (None too when its
    default is None), a time of the day (`HH:MM`), one of `options`, or a short text (None when
    unset), or an order of every one of `options` (a list, each once)."""

    kind: ValueKind
    default: SettingValue
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[int, ...] | None = None
    options: tuple[str, ...] | None = None


@dataclass(frozen=True, kw_only=True)
class SettingsView:
    values: Mapping[str, SettingValue]
    """Every setting of the catalog, the default of those never saved."""
    secrets: Mapping[str, int | None]
    """Every secret of the catalog: when it was set (Unix seconds), None when it is not."""
    torrent_clients: tuple[str, ...] = ()
    """The torrent clients a connector of this version serves, in the order of the catalog."""


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
class TorrentSettings:
    """The settings of the torrent client (`torrent.*`), as its connector reads them
    (`shelfdrop.clients.torrents.client.TorrentConnection`)."""

    client: str
    url: str | None
    username: str | None
    password: str | None
    api_key: str | None


@dataclass(frozen=True, kw_only=True)
class ProbeResult:
    """What a test of a connection found: `connected`, or why not: `no_address`, `no_key` (a
    secret, or for a torrent client a credential it needs, is missing), `refused`,
    `unavailable` (no answer), and for the torrent client `unsupported` (it answers, but
    shelfdrop cannot send to it: `reason`) or `no_connector` (no connector of this version serves
    the client chosen)."""

    service: str
    state: ProbeState
    status: int | None = None
    """The HTTP status of a refusal or of an error."""
    version: str | None = None
    count: int | None = None
    """Prowlarr: the indexers on; the torrent client: the categories of shelfdrop found;
    Jellyfin: the libraries of books."""
    missing: tuple[str, ...] = ()
    """The torrent client: the categories of shelfdrop it does not have."""
    elapsed_ms: int | None = None
    """A metadata source: the time of its answer."""
    client: str | None = None
    """The torrent client tested (`torrent.client`)."""
    reason: str | None = None
    """`unsupported`: why, as the connector names it (`label-plugin`, `transmission-version`)."""

    @property
    def ok(self) -> bool:
        return self.state == "connected"
