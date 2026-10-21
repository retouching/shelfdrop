"""The answers of Prowlarr the tests replay: its indexers and its releases for a few names.

No real Prowlarr is ever asked by a test (the one of the user is not to be called): these
answers are written in the shape of the API v1 of Prowlarr (its OpenAPI document,
`ReleaseResource` and `IndexerResource`), with release titles seen on the trackers of the user
(PapriKa+, ebdz, NEO, Kuppit, the packs of Nyaa). `prowlarr.json` holds them; the unit tests
read them through `ProwlarrReplay`, the integration tests load them into the fake sources.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final, override

import httpx

from shelfdrop.releases.clients.prowlarr import ProwlarrClient, fixed
from shelfdrop.releases.jobs import ReleaseSource, SearchBoard
from shelfdrop.releases.repository import ReleaseRepository
from shelfdrop.releases.types import FilterRule, FoundRelease, ReleaseOptions, Tracker
from shelfdrop.works.types import Clock
from tests.unit.settings.support import FakeSettingsReader
from tests.unit.support import no_session
from tests.unit.works.support import FixedClock

FIXTURE: Final = Path(__file__).parent / "fixtures" / "prowlarr.json"
API_KEY: Final = "test-prowlarr-key"
URL: Final = "http://prowlarr.test"


def load() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text("utf-8"))
    return data


class ProwlarrReplay:
    """An `httpx.MockTransport` handler that answers like Prowlarr from `prowlarr.json`, and
    keeps every request it got. A search it does not know finds nothing."""

    def __init__(self) -> None:
        self.data = load()
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("X-Api-Key") != API_KEY:
            return httpx.Response(401, request=request)
        if request.url.path == "/api/v1/system/status":
            return httpx.Response(200, json=self.data["status"], request=request)
        if request.url.path == "/api/v1/indexer":
            return httpx.Response(200, json=self.data["indexers"], request=request)
        if request.url.path == "/api/v1/search":
            query = request.url.params.get("query")
            categories = [int(c) for c in request.url.params.get_list("categories")]
            for search in self.data["searches"]:
                if search["query"] == query and search["categories"] == categories:
                    return httpx.Response(200, json=search["releases"], request=request)
            return httpx.Response(200, json=[], request=request)
        return httpx.Response(404, request=request)

    def searched(self) -> list[str]:
        return [
            str(r.url.params.get("query")) for r in self.requests if r.url.path == "/api/v1/search"
        ]


class FakeReleaseRepository(ReleaseRepository):
    """The tables in memory; it counts the commits. One instance plays every session."""

    def __init__(self) -> None:
        super().__init__(no_session())
        self.audit: list[tuple[str, str]] = []
        self.answers: dict[str, tuple[tuple[FoundRelease, ...], float, int]] = {}
        self.trackers: list[Tracker] = []
        self.rules: tuple[FilterRule, ...] = ()
        self.settings: dict[str, object] = {}
        self.commits = 0

    @override
    def read_answer(self, key: str, now: int) -> tuple[tuple[FoundRelease, ...], float] | None:
        found = self.answers.get(key)
        return None if found is None or found[2] <= now else (found[0], found[1])

    @override
    def save_answer(
        self, key: str, releases: tuple[FoundRelease, ...], fetched_at: float, expires_at: int
    ) -> None:
        self.answers[key] = (releases, fetched_at, expires_at)

    @override
    def remove_expired_answers(self, now: int) -> None:
        self.answers = {k: v for k, v in self.answers.items() if v[2] > now}

    @override
    def read_trackers(self) -> list[Tracker]:
        return list(self.trackers)

    @override
    def replace_trackers(self, trackers: Iterable[Tracker]) -> None:
        self.trackers = list(trackers)

    @override
    def read_rules(self) -> tuple[FilterRule, ...]:
        return self.rules

    @override
    def replace_rules(self, rules: Iterable[FilterRule]) -> None:
        self.rules = tuple(rules)

    @override
    def read_setting(self, key: str) -> object | None:
        return self.settings.get(key)

    @override
    def save_setting(self, key: str, value: object, now: int, actor: str) -> None:
        self.settings[key] = value

    @override
    def add_audit(self, at: int, actor: str, target: str) -> None:
        self.audit.append((actor, target))

    @override
    def commit(self) -> None:
        self.commits += 1

    @override
    def close(self) -> None:
        pass


def new_prowlarr(handler: ProwlarrReplay | None = None) -> tuple[ProwlarrClient, ProwlarrReplay]:
    replay = handler or ProwlarrReplay()
    http = httpx.AsyncClient(transport=httpx.MockTransport(replay))
    return ProwlarrClient(http, fixed(URL, API_KEY)), replay


def new_board(
    source: ReleaseSource,
    repository: FakeReleaseRepository,
    *,
    options: ReleaseOptions | None = None,
    clock: Clock | None = None,
) -> SearchBoard:
    return SearchBoard(
        source,
        lambda: repository,
        options or ReleaseOptions(),
        clock or FixedClock(),
        FakeSettingsReader(),
    )
