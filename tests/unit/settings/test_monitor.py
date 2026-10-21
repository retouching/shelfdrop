"""shelfdrop.settings.monitor: the services saved tested in the background, a failure logged
once."""

import logging

import pytest

from shelfdrop.settings.monitor import ConnectionMonitor
from shelfdrop.settings.types import ProbeResult
from tests.unit.settings.support import FakeSettingsReader
from tests.unit.works.support import FixedClock


class ScriptedProbes:
    def __init__(self) -> None:
        self.state = "connected"
        self.asked: list[str] = []

    def names(self) -> tuple[str, ...]:
        return ("prowlarr", "qbittorrent", "jellyfin")

    async def run(self, service: str, url: str | None, secret: str | None) -> ProbeResult:
        self.asked.append(service)
        return ProbeResult(service=service, state=self.state, status=503)  # type: ignore[arg-type]  # the state scripted by the test is a ProbeState


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_only_the_services_saved_are_tested_and_a_failure_is_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probes = ScriptedProbes()
    reader = FakeSettingsReader(
        {"prowlarr.url": "http://p:9696", "jellyfin.url": "http://j:8096"},
        {"prowlarr.api_key": "k"},
    )
    monitor = ConnectionMonitor(probes, reader, FixedClock())
    caplog.set_level(logging.INFO, logger="shelfdrop.settings.monitor")

    await monitor.check_all()
    probes.state = "unavailable"
    await monitor.check_all()
    await monitor.check_all()
    probes.state = "connected"
    await monitor.check_all()

    assert probes.asked == ["prowlarr"] * 4
    messages = [record.getMessage() for record in caplog.records]
    assert messages == ["Service unavailable", "Service available again"]
    results, checked_at = monitor.last()
    assert [r.service for r in results] == ["prowlarr"]
    assert results[0].ok
    assert checked_at == int(FixedClock().now())
