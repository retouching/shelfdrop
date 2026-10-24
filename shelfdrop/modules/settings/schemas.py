"""Request and response schemas of the settings module. A secret is never in a response: only
when it was set."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shelfdrop.settings.types import ProbeState

# An order (`search.language_order`, `search.source_order`) is a list of every value it orders.
type Value = str | int | bool | list[str] | None


class SettingsRead(BaseModel):
    # Every setting of the catalog (shelfdrop.settings.catalog), its default when never saved.
    values: dict[str, Value]
    # Every secret: when it was set (Unix seconds), or null.
    secrets: dict[str, int | None]
    # The torrent clients this version can use (`torrent.client`), in the order of the catalog.
    torrent_clients: list[str]


class SettingsUpdate(BaseModel):
    # The settings changed; the others stay.
    values: dict[str, Value] = Field(default_factory=dict)
    # A new value, or null to clear the secret.
    secrets: dict[str, str | None] = Field(default_factory=dict)


class ProbeBody(BaseModel):
    # prowlarr, torrent (the torrent client), jellyfin, or a source (kitsu, myanimelist...).
    service: str = Field(min_length=1, max_length=40)
    # The address typed; null: the one saved. A source has none.
    url: str | None = None
    # The key typed; null: the one saved; "": none (cleared on the page, not saved yet). The
    # torrent client: the key of qui, the password of the others; the one saved is the one of
    # the client tested.
    secret: str | None = Field(default=None, max_length=1000)
    # The torrent client alone: the client typed (qui, qbittorrent, deluge, transmission);
    # null: the one saved.
    client: str | None = Field(default=None, max_length=40)
    # The torrent client alone: the username typed; null: the one saved; "": none.
    username: str | None = Field(default=None, max_length=255)


class ProbeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service: str
    ok: bool
    state: ProbeState
    status: int | None
    version: str | None
    count: int | None
    missing: list[str]
    elapsed_ms: int | None
    # The torrent client tested; null for the other services.
    client: str | None
    # `unsupported`: why shelfdrop cannot send to the torrent client (`label-plugin`: Deluge
    # without its plugin Label, `transmission-version`: Transmission before 3.00).
    reason: str | None


class HealthRead(BaseModel):
    # The last background test of each service saved, every 5 minutes.
    services: list[ProbeRead]
    checked_at: int | None


class AuditEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    at: int
    actor: str
    action: Literal["changed", "replaced", "cleared", "imported", "created", "revoked"]
    target: str


class AuditRead(BaseModel):
    entries: list[AuditEntryRead]
