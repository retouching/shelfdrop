"""The routes of the settings page: read and change the settings and their secrets, test a
connection, the last background tests, the audit. Async: a test waits on its service."""

from typing import Annotated

from fastapi import APIRouter, Depends
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import require_session
from shelfdrop.modules.settings.errors import invalid_settings
from shelfdrop.modules.settings.schemas import (
    AuditEntryRead,
    AuditRead,
    HealthRead,
    ProbeBody,
    ProbeRead,
    SettingsRead,
    SettingsUpdate,
)
from shelfdrop.settings.exceptions import InvalidSettingsError
from shelfdrop.settings.service import SettingsService
from shelfdrop.settings.types import ProbeResult, SettingsChange, SettingsView

router = APIRouter(prefix="/v1/settings", tags=["settings"], route_class=WireupRoute)


def settings_read(view: SettingsView) -> SettingsRead:
    return SettingsRead(values=dict(view.values), secrets=dict(view.secrets))


def probe_read(result: ProbeResult) -> ProbeRead:
    return ProbeRead(
        service=result.service,
        ok=result.ok,
        state=result.state,
        status=result.status,
        version=result.version,
        count=result.count,
        missing=list(result.missing),
        elapsed_ms=result.elapsed_ms,
    )


@router.get("")
async def read_settings(service: Injected[SettingsService]) -> SettingsRead:
    return settings_read(await service.read())


@router.put("")
async def save_settings(
    service: Injected[SettingsService],
    account: Annotated[Account, Depends(require_session)],
    body: SettingsUpdate,
) -> SettingsRead:
    change = SettingsChange(values=body.values, secrets=body.secrets)
    try:
        return settings_read(await service.save(change, account.username))
    except InvalidSettingsError as exc:
        raise invalid_settings(exc.keys) from exc


@router.post("/test")
async def test_connection(service: Injected[SettingsService], body: ProbeBody) -> ProbeRead:
    """Test a service or a source with the values typed, before they are saved."""
    try:
        return probe_read(await service.test(body.service, body.url, body.secret))
    except InvalidSettingsError as exc:
        raise invalid_settings(exc.keys) from exc


@router.get("/health")
async def read_health(service: Injected[SettingsService]) -> HealthRead:
    results, checked_at = service.health()
    return HealthRead(services=[probe_read(r) for r in results], checked_at=checked_at)


@router.get("/audit")
async def read_audit(service: Injected[SettingsService]) -> AuditRead:
    entries = await service.read_audit()
    return AuditRead(entries=[AuditEntryRead.model_validate(e) for e in entries])
