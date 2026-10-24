"""ConnectionMonitor: the tests of the services saved, every 5 minutes in the background, the last
result of each kept in memory for the page. A container singleton; the lifespan of the application
runs it.

A service is tested once its address and its key are saved; the torrent client once its address
is (Transmission may sign in with nothing; its test names a credential missing). A failure is
logged once, when it starts, and its end once.
"""

import logging
from typing import Final, Protocol

import anyio

from shelfdrop.settings.catalog import SERVICES
from shelfdrop.settings.types import ProbeResult
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)

EVERY_SECONDS: Final = 300.0


class Prober(Protocol):
    async def run(self, service: str, url: str | None, secret: str | None) -> ProbeResult: ...


class SavedConnections(Protocol):
    async def connection(self, service: str) -> tuple[str | None, str | None]: ...


class ConnectionMonitor:
    def __init__(self, probes: Prober, saved: SavedConnections, clock: Clock) -> None:
        self.probes = probes
        self.saved = saved
        self.clock = clock
        self.results: dict[str, ProbeResult] = {}
        self.checked_at: int | None = None

    async def check_all(self) -> None:
        for service in SERVICES:
            url, secret = await self.saved.connection(service)
            if not url or (not secret and service != "torrent"):
                self.results.pop(service, None)
                continue
            result = await self.probes.run(service, url, secret)
            before = self.results.get(service)
            if not result.ok and (before is None or before.ok):
                logger.warning(
                    "Service unavailable",
                    extra={"service": service, "state": result.state, "status": result.status},
                )
            elif result.ok and before is not None and not before.ok:
                logger.info("Service available again", extra={"service": service})
            self.results[service] = result
        self.checked_at = int(self.clock.now())

    async def run(self) -> None:
        """Forever, until cancelled; a failure of a round is logged, and the next one comes."""
        while True:
            try:
                await self.check_all()
            except Exception:
                logger.exception("Connection checks failed")
            await anyio.sleep(EVERY_SECONDS)

    def last(self) -> tuple[list[ProbeResult], int | None]:
        """The last result of each service tested, and when."""
        return [self.results[s] for s in SERVICES if s in self.results], self.checked_at
