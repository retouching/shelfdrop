"""The state of the work search shared by every request: the searches running now and the
sources that failed lately. One instance per process (a container singleton)."""

import asyncio

from shelfdrop.works.types import SourceName, WorkSearch


class SearchFlights:
    """Two identical searches at the same time share one run: the second waits for the first."""

    def __init__(self) -> None:
        self.running: dict[str, asyncio.Future[WorkSearch]] = {}

    def joined(self, key: str) -> asyncio.Future[WorkSearch] | None:
        return self.running.get(key)

    def start(self, key: str) -> asyncio.Future[WorkSearch]:
        future: asyncio.Future[WorkSearch] = asyncio.get_running_loop().create_future()
        self.running[key] = future
        return future

    def end(self, key: str) -> None:
        self.running.pop(key, None)


class SourceHealth:
    """A source that failed is skipped until a moment given in Unix seconds, so that a source
    that is down does not slow every search down."""

    def __init__(self) -> None:
        self.down_until: dict[SourceName, float] = {}

    def is_down(self, source: SourceName, now: float) -> bool:
        return self.down_until.get(source, 0.0) > now

    def failed(self, source: SourceName, until: float) -> None:
        self.down_until[source] = until
