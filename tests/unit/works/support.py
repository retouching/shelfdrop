"""Fakes of the work search: the replay of the recorded exchanges of the sources, a repository
in memory, a clock and a service built on them.

`tests/unit/works/record.py` runs the real searches through `RecordingTransport` and writes one
JSON file per case; the tests replay them with `ReplayTransport`, without network. An exchange
that failed while recording (timeout, connection error) is replayed as the same failure.
"""

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final, override
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx

from shelfdrop.config import Settings
from shelfdrop.container import new_work_sources
from shelfdrop.works.flights import SearchFlights, SourceHealth
from shelfdrop.works.repository import WorkRepository
from shelfdrop.works.service import WorkService, WorkSources
from shelfdrop.works.types import Candidate, Clock, SearchOptions, SourceName, Work
from tests.unit.support import no_session

FIXTURES: Final = Path(__file__).parent / "fixtures"
NOW: Final = 1_792_000_000.0


def request_key(request: httpx.Request) -> str:
    parts = urlsplit(str(request.url))
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    body = request.content.decode("utf-8", "replace") if request.content else ""
    return f"{request.method} {parts.scheme}://{parts.netloc}{parts.path}?{query} {body}"


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.inner = httpx.AsyncHTTPTransport(retries=0)
        self.exchanges: dict[str, dict[str, Any]] = {}

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        key = request_key(request)
        try:
            response = await self.inner.handle_async_request(request)
            content = await response.aread()
        except httpx.HTTPError as exc:
            self.exchanges[key] = {"error": type(exc).__name__}
            raise
        except BaseException:
            # Cancelled by the deadline of the source: replayed as a timeout.
            self.exchanges[key] = {"error": "timeout"}
            raise
        self.exchanges[key] = {
            "status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "body": content.decode("utf-8", "replace"),
        }
        return httpx.Response(
            response.status_code,
            headers={"content-type": self.exchanges[key]["content_type"]},
            content=content,
            request=request,
        )


class ReplayTransport(httpx.AsyncBaseTransport):
    def __init__(self, exchanges: dict[str, dict[str, Any]]) -> None:
        self.exchanges = exchanges
        self.missing: list[str] = []

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        key = request_key(request)
        exchange = self.exchanges.get(key)
        if exchange is None:
            self.missing.append(key)
            return httpx.Response(503, request=request)
        if "error" in exchange:
            raise httpx.ConnectTimeout(exchange["error"], request=request)
        return httpx.Response(
            exchange["status"],
            headers={"content-type": exchange["content_type"]},
            content=exchange["body"].encode("utf-8"),
            request=request,
        )


def load(slug: str) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = json.loads((FIXTURES / f"{slug}.json").read_text("utf-8"))
    return data


def save(slug: str, exchanges: dict[str, dict[str, Any]]) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    text = json.dumps(exchanges, ensure_ascii=False, indent=1, sort_keys=True)
    (FIXTURES / f"{slug}.json").write_text(text + "\n", "utf-8")


class FakeWorkRepository(WorkRepository):
    """The cache in memory; it counts the commits."""

    def __init__(self) -> None:
        super().__init__(no_session())
        self.answers: dict[tuple[SourceName, str], tuple[tuple[Candidate, ...], int]] = {}
        self.works: dict[str, tuple[Work, int]] = {}
        self.commits = 0

    @override
    def read_answers(
        self, sources: Iterable[SourceName], query: str, now: int
    ) -> dict[SourceName, tuple[Candidate, ...]]:
        found: dict[SourceName, tuple[Candidate, ...]] = {}
        for source in sources:
            answer = self.answers.get((source, query))
            if answer is not None and answer[1] > now:
                found[source] = answer[0]
        return found

    @override
    def save_answers(
        self, answers: Mapping[SourceName, tuple[Candidate, ...]], query: str, expires_at: int
    ) -> None:
        for source, candidates in answers.items():
            self.answers[source, query] = (candidates, expires_at)

    @override
    def save_works(self, works: Iterable[Work], expires_at: int) -> None:
        for work in works:
            self.works[work.id] = (work, expires_at)

    @override
    def read_work(self, work_id: str, now: int) -> Work | None:
        found = self.works.get(work_id)
        return found[0] if found is not None and found[1] > now else None

    @override
    def remove_expired(self, now: int) -> None:
        self.answers = {key: value for key, value in self.answers.items() if value[1] > now}
        self.works = {key: value for key, value in self.works.items() if value[1] > now}

    @override
    def commit(self) -> None:
        self.commits += 1


class FixedClock(Clock):
    def __init__(self, now: float = NOW) -> None:
        self.at = now

    @override
    def now(self) -> float:
        return self.at


def new_service(
    sources: WorkSources,
    *,
    repository: WorkRepository | None = None,
    flights: SearchFlights | None = None,
    health: SourceHealth | None = None,
    clock: Clock | None = None,
) -> WorkService:
    return WorkService(
        repository or FakeWorkRepository(),
        sources,
        flights or SearchFlights(),
        health or SourceHealth(),
        SearchOptions(),
        clock or FixedClock(),
    )


TEST_SETTINGS: Final = Settings(_env_file=None, contact="tests@shelfdrop.invalid")


def replayed_service(http: httpx.AsyncClient) -> WorkService:
    """The sources of a deployment without a MyAnimeList Client ID, the one of the fixtures."""
    return new_service(new_work_sources(http, TEST_SETTINGS))
