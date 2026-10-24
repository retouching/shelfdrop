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
    """A source that failed several times in a row is skipped until a moment given in Unix
    seconds, so that a source that is down does not slow every search down, while one slow
    answer does not leave it out."""

    def __init__(self) -> None:
        self.down_until: dict[SourceName, float] = {}
        self.failures: dict[SourceName, int] = {}

    def is_down(self, source: SourceName, now: float) -> bool:
        return self.down_until.get(source, 0.0) > now

    def failed(self, source: SourceName, until: float, failures_to_rest: int = 1) -> None:
        """One more failure of `source` in a row; at `failures_to_rest`, it rests until
        `until` and its count starts again."""
        count = self.failures.get(source, 0) + 1
        if count >= failures_to_rest:
            self.down_until[source] = until
            count = 0
        self.failures[source] = count

    def answered(self, source: SourceName) -> None:
        self.failures.pop(source, None)
