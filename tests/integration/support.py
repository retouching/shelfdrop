"""What the integration tests share: the Compose project of the test stack, its logs, and the fake
metadata sources that replay the recorded exchanges of `tests/unit/works/fixtures/`."""

import base64
import json
import os
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qsl, urlsplit

import httpx

PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
COMPOSE_FILES: Final = ("docker/compose.yaml", "docker/compose.test.yaml")
FIXTURES: Final = PROJECT_ROOT / "tests" / "unit" / "works" / "fixtures"
PROWLARR_FIXTURE: Final = (
    PROJECT_ROOT / "tests" / "unit" / "releases" / "fixtures" / "prowlarr.json"
)
PROWLARR_KEY: Final = "test-prowlarr-key"
# The accounts of the fake Jellyfin: an administrator, and an account that is not one.
ADMIN: Final = ("admin", "admin-password-0d1f")
READER: Final = ("reader", "reader-password-5e2a")
JELLYFIN_ADMIN_TOKEN: Final = "jellyfin-admin-token"
SESSION_COOKIE: Final = "__Host-shelfdrop"
JELLYFIN_API_KEY: Final = "jellyfin-api-key-of-the-tests"
QUI_KEY: Final = "qui-client-key-of-the-tests"
# The libraries of the fake Jellyfin: their name, and their folder, `/files/<folder>` there and
# `/data/files/<folder>` for the placement worker.
LIBRARIES: Final = (("BD & Mangas", "comics"), ("Livres", "ebooks"), ("Livres audio", "audiobooks"))
SEPARATOR: Final = " \u203a "
FAKE_ORIGIN: Final = "http://fake-sources:8080"
UP_TIMEOUT_SECONDS: Final = 900
COMMAND_TIMEOUT_SECONDS: Final = 120
LOG_READ_ATTEMPTS: Final = 20
# Every variable docker/compose.yaml requires, given to every Compose call: the stack never
# reads the .env of the developer.
STACK_ENVIRONMENT: Final = {
    "SHELFDROP_CONTACT": "tests@shelfdrop.invalid",
    "SHELFDROP_SECRET_KEY": "test-secret-key-of-the-test-stack-0123456789",
}
ORIGINAL_ORIGIN: Final = "X-Original-Origin"


def compose_command(project: str, *args: str) -> list[str]:
    """The `docker compose` command line of the test project, ending with `args`."""
    command = ["docker", "compose", "--project-name", project]
    for compose_file in COMPOSE_FILES:
        command += ["--file", str(PROJECT_ROOT / compose_file)]
    return [*command, *args]


def compose(
    project: str, *args: str, timeout: float = COMMAND_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        compose_command(project, *args),
        cwd=PROJECT_ROOT,
        env={**os.environ, **STACK_ENVIRONMENT},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def parse_log_records(text: str) -> list[dict[str, Any]]:
    """The JSON records of `docker compose logs --no-log-prefix`; other lines are skipped."""
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def published(project: str, service: str, port: str) -> str:
    """`http://127.0.0.1:<port>`, where `port` of `service` is published."""
    result = compose(project, "port", service, port)
    address = result.stdout.strip()
    if result.returncode != 0 or not address:
        msg = f"cannot resolve the port {port} of {service} in {project}"
        raise RuntimeError(msg)
    return f"http://{address}"


@dataclass
class Stack:
    project: str
    base_url: str = ""
    sources_url: str = ""

    def read_ports(self) -> None:
        """The published ports: at the start, and again after a restart, which draws new ones."""
        self.base_url = published(self.project, "api", "8000")
        self.sources_url = published(self.project, "fake-sources", "8080")

    def api_logs(self) -> str:
        result = compose(self.project, "logs", "--no-color", "--no-log-prefix", "api")
        return result.stdout + result.stderr

    def log_records(self, request_id: str, *, expected: int) -> list[dict[str, Any]]:
        """The JSON records of the API carrying `request_id`. A record written just before the
        response may not be readable yet: the logs are read again (each read is a Compose call,
        no sleep) until `expected` are there."""
        records: list[dict[str, Any]] = []
        for _ in range(LOG_READ_ATTEMPTS):
            records = [
                record
                for record in parse_log_records(self.api_logs())
                if record.get("request_id") == request_id
            ]
            if len(records) >= expected:
                break
        return records

    def exec_api(self, *command: str) -> subprocess.CompletedProcess[str]:
        """Run `command` in the container of the API."""
        return compose(self.project, "exec", "-T", "api", *command)

    def exec_placement(self, *command: str, root: bool = False) -> subprocess.CompletedProcess[str]:
        """Run `command` in the container of the placement worker (as root with `root`), which
        sees the torrents and the libraries of the tests under /data."""
        user = ["--user", "0:0"] if root else []
        result = compose(self.project, "exec", "-T", *user, "placement", *command)
        assert result.returncode == 0, result.stderr
        return result


def stub_of(key: str, exchange: dict[str, Any]) -> dict[str, Any]:
    """The WireMock stub of one recorded exchange (`tests.unit.works.support.request_key`):
    the same method, origin, path, query and body get the recorded answer; a failure recorded
    (a timeout, a refused connection) is replayed as a reset connection."""
    method, rest = key.split(" ", 1)
    url, _, body = rest.partition(" ")
    parts = urlsplit(url)
    request: dict[str, Any] = {
        "method": method,
        "urlPath": parts.path or "/",
        "headers": {ORIGINAL_ORIGIN: {"equalTo": f"{parts.scheme}://{parts.netloc}"}},
    }
    query = parse_qsl(parts.query, keep_blank_values=True)
    if query:
        request["queryParameters"] = {name: {"equalTo": value} for name, value in query}
    if body:
        request["bodyPatterns"] = [{"equalToJson": body}]
    if "error" in exchange:
        response: dict[str, Any] = {"fault": "CONNECTION_RESET_BY_PEER"}
    else:
        response = {
            "status": exchange["status"],
            "headers": {"Content-Type": exchange["content_type"]},
            "body": exchange["body"],
        }
    return {"request": request, "response": response}


def recorded_stubs() -> list[dict[str, Any]]:
    """The stubs of every recorded exchange of every case, once each."""
    stubs: dict[str, dict[str, Any]] = {}
    for path in sorted(FIXTURES.glob("*.json")):
        exchanges: dict[str, dict[str, Any]] = json.loads(path.read_text("utf-8"))
        for key, exchange in exchanges.items():
            stubs[key] = stub_of(key, exchange)
    return list(stubs.values())


def prowlarr_search_stub(
    query: str, categories: list[int], releases: list[dict[str, Any]], *, delay_ms: int = 0
) -> dict[str, Any]:
    """Prowlarr answers `releases` to a search of `query` in `categories`, after `delay_ms`."""
    response: dict[str, Any] = {
        "status": 200,
        "headers": {"Content-Type": "application/json"},
        "jsonBody": releases,
    }
    if delay_ms:
        response["fixedDelayMilliseconds"] = delay_ms
    return {
        "priority": 1,
        "request": {
            "method": "GET",
            "urlPath": "/api/v1/search",
            "headers": {"X-Api-Key": {"equalTo": PROWLARR_KEY}},
            "queryParameters": {
                "query": {"equalTo": query},
                "categories": {"hasExactly": [{"equalTo": str(c)} for c in categories]},
            },
        },
        "response": response,
    }


def prowlarr_stubs() -> list[dict[str, Any]]:
    """Prowlarr as `tests/unit/releases/fixtures/prowlarr.json` plays it: its indexers, its
    answers, and nothing found for any other search (a stub of a lower priority)."""
    data: dict[str, Any] = json.loads(PROWLARR_FIXTURE.read_text("utf-8"))
    key = {"X-Api-Key": {"equalTo": PROWLARR_KEY}}
    stubs: list[dict[str, Any]] = [
        {
            "request": {"method": "GET", "urlPath": "/api/v1/system/status", "headers": key},
            "response": {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": data["status"],
            },
        },
        {
            "request": {"method": "GET", "urlPath": "/api/v1/indexer", "headers": key},
            "response": {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": data["indexers"],
            },
        },
        {
            "priority": 10,
            "request": {"method": "GET", "urlPath": "/api/v1/search", "headers": key},
            "response": {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": [],
            },
        },
    ]
    stubs += [
        prowlarr_search_stub(search["query"], search["categories"], search["releases"])
        for search in data["searches"]
    ]
    # Another key: Prowlarr refuses it.
    stubs.append(
        {
            "priority": 20,
            "request": {"method": "GET", "urlPathPattern": "/api/v1/.*"},
            "response": {"status": 401},
        }
    )
    return stubs


def jellyfin_user(user_id: str, name: str, *, admin: bool) -> dict[str, Any]:
    """A `UserDto` of Jellyfin (its OpenAPI document)."""
    return {
        "Name": name,
        "Id": user_id,
        "HasPassword": True,
        "Policy": {"IsAdministrator": admin, "IsDisabled": False},
    }


def json_response(body: object, status: int = 200) -> dict[str, Any]:
    return {"status": status, "headers": {"Content-Type": "application/json"}, "jsonBody": body}


def jellyfin_stubs() -> list[dict[str, Any]]:
    """Jellyfin as the fake sources play it: the sign-in of the two accounts (any other is
    refused), the account of the access token of the administrator, the sign-out."""
    accounts = [
        (ADMIN, jellyfin_user("a1f0c3", "admin", admin=True), JELLYFIN_ADMIN_TOKEN),
        (READER, jellyfin_user("b2e1d4", "reader", admin=False), "jellyfin-reader-token"),
    ]
    stubs: list[dict[str, Any]] = [
        {
            "priority": 1,
            "request": {
                "method": "POST",
                "urlPath": "/Users/AuthenticateByName",
                "bodyPatterns": [{"equalToJson": {"Username": name, "Pw": password}}],
            },
            "response": json_response({"User": user, "AccessToken": token, "ServerId": "f0"}),
        }
        for (name, password), user, token in accounts
    ]
    stubs += [
        {
            "priority": 10,
            "request": {"method": "POST", "urlPath": "/Users/AuthenticateByName"},
            "response": {"status": 401},
        },
        {
            "priority": 1,
            "request": {
                "method": "GET",
                "urlPath": "/Users/Me",
                "headers": {"Authorization": {"contains": f'Token="{JELLYFIN_ADMIN_TOKEN}"'}},
            },
            "response": json_response(accounts[0][1]),
        },
        {
            "priority": 10,
            "request": {"method": "GET", "urlPath": "/Users/Me"},
            "response": {"status": 401},
        },
        {
            "request": {"method": "POST", "urlPath": "/Sessions/Logout"},
            "response": {"status": 204},
        },
    ]
    key = {"Authorization": {"contains": f'Token="{JELLYFIN_API_KEY}"'}}
    libraries = [
        {
            "Name": name,
            "CollectionType": "books",
            "ItemId": f"lib-{folder}",
            "Locations": [f"/files/{folder}"],
        }
        for name, folder in LIBRARIES
    ]
    libraries.append(
        {
            "Name": "Films",
            "CollectionType": "movies",
            "ItemId": "lib-movies",
            "Locations": ["/movies"],
        }
    )
    stubs += [
        {
            "priority": 1,
            "request": {"method": "GET", "urlPath": "/System/Info", "headers": key},
            "response": json_response({"Version": "10.11.2", "ServerName": "nami"}),
        },
        {
            "priority": 1,
            "request": {"method": "GET", "urlPath": "/Library/VirtualFolders", "headers": key},
            "response": json_response(libraries),
        },
        *(
            {
                "priority": 10,
                "request": {"method": "GET", "urlPath": path},
                "response": {"status": 401},
            }
            for path in ("/System/Info", "/Library/VirtualFolders")
        ),
    ]
    return stubs


QUI_PROXY: Final = f"/proxy/{QUI_KEY}/api/v2"


QBITTORRENT_LISTS: Final = "http://qbittorrent-lists:8080"
# The mark of the requests of one hash `qbittorrent-lists` sends (its `PART_HEADER`): not those of
# the API, `FakeSources.requests` leaves them out.
PART_HEADER: Final = "X-Fake-Part"


def qbittorrent_stubs() -> list[dict[str, Any]]:
    """qBittorrent behind the client proxy of qui, as the fake sources play it: its version and
    three of the four categories of shelfdrop under the key of the tests, no torrent but those a
    test adds (`torrent_stubs`), each torrent of a list of several hashes (`hashes=<a>|<b>`), a
    401 under another key."""
    proxy = QUI_PROXY
    categories = {
        name: {"name": name, "savePath": f"/data/{name}"}
        for name in ("manga", "ebook", "audiobook")
    }
    return [
        {
            "priority": 1,
            "request": {"method": "GET", "urlPath": f"{proxy}/app/version"},
            "response": {
                "status": 200,
                "headers": {"Content-Type": "text/plain"},
                "body": "v5.1.2",
            },
        },
        {
            "priority": 1,
            "request": {"method": "GET", "urlPath": f"{proxy}/torrents/categories"},
            "response": json_response(categories),
        },
        # A list of several hashes: the torrents of each, joined by the service
        # `qbittorrent-lists` (tests/integration/qbittorrent_lists.py), as qBittorrent lists them.
        {
            "priority": 2,
            "request": {
                "method": "GET",
                "urlPath": f"{proxy}/torrents/info",
                "queryParameters": {"hashes": {"contains": "|"}},
            },
            "response": {"proxyBaseUrl": QBITTORRENT_LISTS},
        },
        {
            "priority": 5,
            "request": {"method": "GET", "urlPath": f"{proxy}/torrents/info"},
            "response": json_response([]),
        },
        {
            "priority": 10,
            "request": {"method": "GET", "urlPathPattern": "/proxy/.*"},
            "response": {"status": 401},
        },
    ]


def torrent_info(digest: str, **fields: object) -> dict[str, Any]:
    """A torrent of `GET /api/v2/torrents/info` (the WebUI API of qBittorrent 5.0)."""
    return {
        "hash": digest,
        "name": digest,
        "category": "",
        "state": "downloading",
        "progress": 0.0,
        "dlspeed": 0,
        "eta": 8640000,
        **fields,
    }


def torrent_stubs(
    digest: str,
    name: str,
    *,
    lost: bool = False,
    added: dict[str, Any] | None = None,
    complete: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """qBittorrent and the torrent `digest` (its file names `name`), in a scenario of its own:
    not listed until an add of it; `lost`, the first add is accepted and lost. Added, it is
    listed with the fields `added`; `POST /tests/complete/<digest>` on the fake sources makes
    it listed with the fields `complete`."""
    scenario = f"torrent-{digest}"
    info = {"method": "GET", "urlPath": f"{QUI_PROXY}/torrents/info"}
    # Its hash alone: a list of several goes to `qbittorrent-lists`, which asks for each.
    hashes = {"hashes": {"equalTo": digest}}
    add = {
        "method": "POST",
        "urlPath": f"{QUI_PROXY}/torrents/add",
        "bodyPatterns": [{"contains": name}],
    }
    ok = {"status": 200, "headers": {"Content-Type": "text/plain"}, "body": "Ok."}
    stubs: list[dict[str, Any]] = [
        {
            "priority": 1,
            "scenarioName": scenario,
            "requiredScenarioState": "Started",
            "newScenarioState": "lost" if lost else "added",
            "request": add,
            "response": ok,
        },
        {
            "priority": 1,
            "scenarioName": scenario,
            "requiredScenarioState": "lost",
            "newScenarioState": "added",
            "request": add,
            "response": ok,
        },
        {
            "priority": 1,
            "scenarioName": scenario,
            "requiredScenarioState": "added",
            "request": {**info, "queryParameters": hashes},
            "response": json_response([torrent_info(digest, **(added or {}))]),
        },
        {
            "priority": 1,
            "scenarioName": scenario,
            "requiredScenarioState": "added",
            "newScenarioState": "complete",
            "request": {"method": "POST", "urlPath": f"/tests/complete/{digest}"},
            "response": {"status": 200},
        },
        {
            "priority": 1,
            "scenarioName": scenario,
            "requiredScenarioState": "complete",
            "request": {**info, "queryParameters": hashes},
            "response": json_response(
                [torrent_info(digest, **(complete or {"state": "stalledUP", "progress": 1.0}))]
            ),
        },
    ]
    return stubs


def prowlarr_release(
    guid: str, title: str, link: str, *, indexer_id: int = 1, indexer: str = "Nyaa.si"
) -> dict[str, Any]:
    """A release of `GET /api/v1/search` whose download link, through Prowlarr, carries its
    key, as Prowlarr writes it (`<prowlarr>/<indexer>/download?apikey=...&link=...&file=...`)."""
    return {
        "guid": guid,
        "title": title,
        "indexerId": indexer_id,
        "indexer": indexer,
        "size": 104857600,
        "seeders": 12,
        "leechers": 0,
        "protocol": "torrent",
        "publishDate": "2026-10-20T10:00:00Z",
        "downloadUrl": f"http://prowlarr.test/{indexer_id}/download?apikey={PROWLARR_KEY}"
        f"&link={link}&file={title}",
        "categories": [{"id": 7030, "name": "Books/Comics"}],
    }


def prowlarr_download_stub(indexer_id: int, link: str, data: bytes) -> dict[str, Any]:
    """Prowlarr gives the `.torrent` `data` behind `link`, to its key in the header alone."""
    return {
        "priority": 1,
        "request": {
            "method": "GET",
            "urlPath": f"/{indexer_id}/download",
            "headers": {"X-Api-Key": {"equalTo": PROWLARR_KEY}},
            "queryParameters": {"link": {"equalTo": link}, "apikey": {"absent": True}},
        },
        "response": {
            "status": 200,
            "headers": {"Content-Type": "application/x-bittorrent"},
            "base64Body": base64.b64encode(data).decode(),
        },
    }


def wait_for_download(
    client: httpx.Client, download_id: int, done: Callable[[dict[str, Any]], bool]
) -> dict[str, Any]:
    """The download `download_id` of `GET /api/v1/downloads` once `done` holds: its send goes on
    after its request (looked for in qBittorrent every second in the test stack). Read again
    without sleeping, 30 seconds at most."""
    deadline = time.monotonic() + 30
    found: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get("/api/v1/downloads")
        response.raise_for_status()
        found = next(d for d in response.json()["downloads"] if d["id"] == download_id)
        if done(found):
            return found
    msg = f"download {download_id} never got there: {found}"
    raise AssertionError(msg)


def sign_in(base_url: str, account: tuple[str, str] = ADMIN) -> httpx.Response:
    """`POST /api/v1/session` from the pages of the API (its own Origin)."""
    username, password = account
    return httpx.post(
        f"{base_url}/api/v1/session",
        json={"username": username, "password": password},
        headers={"Origin": base_url},
        timeout=30.0,
    )


def cookie_of(response: httpx.Response) -> str:
    """The token of the session cookie a sign-in set. httpx sends no Secure cookie over plain
    HTTP: the tests send it themselves (`signed_in_headers`)."""
    token = response.cookies.get(SESSION_COOKIE)
    assert token, "no session cookie"
    return token


def new_access_token(client: httpx.Client, scope: str, name: str = "Hermes") -> dict[str, Any]:
    """A token created by the session of `client` (the administrator): `{"token", "secret"}`."""
    response = client.post("/api/v1/tokens", json={"name": name, "scope": scope, "days": 30})
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def bearer(secret: str) -> dict[str, str]:
    """The headers of a client of the API with an access token: no cookie, no Origin."""
    return {"Authorization": f"Bearer {secret}"}


def signed_in_headers(base_url: str, token: str) -> dict[str, str]:
    """The headers of a request of the pages, signed in: the session cookie and the Origin."""
    return {"Cookie": f"{SESSION_COOKIE}={token}", "Origin": base_url}


@dataclass(frozen=True)
class FakeSources:
    """The administration of the WireMock that plays the metadata sources."""

    url: str

    def load(self, stubs: list[dict[str, Any]]) -> None:
        response = httpx.post(
            f"{self.url}/__admin/mappings/import",
            json={
                "mappings": stubs,
                "importOptions": {"duplicatePolicy": "OVERWRITE", "deleteAllNotInImport": False},
            },
            timeout=60.0,
        )
        response.raise_for_status()

    def count(self, origin: str, path: str, *, body_contains: str | None = None) -> int:
        """How many requests meant for `origin` + `path` the fake received."""
        pattern: dict[str, Any] = {
            "urlPath": path,
            "headers": {ORIGINAL_ORIGIN: {"equalTo": origin}},
        }
        if body_contains is not None:
            pattern["bodyPatterns"] = [{"contains": body_contains}]
        response = httpx.post(f"{self.url}/__admin/requests/count", json=pattern, timeout=10.0)
        response.raise_for_status()
        count: int = response.json()["count"]
        return count

    def unmatched(self, *, sources_only: bool = False) -> list[str]:
        """The requests no stub answered: method, original origin and URL. `sources_only`: those
        of the metadata clients alone (with their original origin); the services are asked by
        the tests of the background at start, before the stubs are loaded."""
        response = httpx.get(f"{self.url}/__admin/requests/unmatched", timeout=10.0)
        response.raise_for_status()
        found: list[str] = []
        for request in response.json()["requests"]:
            headers = request.get("headers", {})
            if sources_only and ORIGINAL_ORIGIN not in headers:
                continue
            found.append(f"{request['method']} {headers.get(ORIGINAL_ORIGIN)}{request['url']}")
        return found

    def prowlarr_searches(self, query: str) -> list[dict[str, list[str]]]:
        """The query parameters of every search of `query` Prowlarr received."""
        response = httpx.post(
            f"{self.url}/__admin/requests/find",
            json={
                "method": "GET",
                "urlPath": "/api/v1/search",
                "queryParameters": {"query": {"equalTo": query}},
            },
            timeout=10.0,
        )
        response.raise_for_status()
        found: list[dict[str, list[str]]] = []
        for request in response.json()["requests"]:
            params = request.get("queryParams", {})
            found.append({name: value["values"] for name, value in params.items()})
        return found

    def requests(self, method: str, path: str) -> list[dict[str, Any]]:
        """The requests to `path` the fake received, as its journal keeps them (`url`, `headers`,
        `body`), but those of one hash `qbittorrent-lists` sends."""
        response = httpx.post(
            f"{self.url}/__admin/requests/find",
            json={"method": method, "urlPath": path, "headers": {PART_HEADER: {"absent": True}}},
            timeout=10.0,
        )
        response.raise_for_status()
        found: list[dict[str, Any]] = response.json()["requests"]
        return found

    def post(self, path: str) -> None:
        """A request to the fake itself: a step of a scenario of a test."""
        httpx.post(f"{self.url}{path}", timeout=10.0).raise_for_status()

    def reset_journal(self) -> None:
        httpx.delete(f"{self.url}/__admin/requests", timeout=10.0).raise_for_status()


JELLYFIN_ADMIN_ID: Final = "admin-of-the-api-key"
WEBHOOK_PATH: Final = "/api/webhooks/1/token-of-the-tests"
WEBHOOK: Final = f"{FAKE_ORIGIN}{WEBHOOK_PATH}"


def jellyfin_library_stubs(folder: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The items of the library of `folder` of the fake Jellyfin (`GET /Items?parentId=`), each
    readable and writable by its id, and the scans of the library."""
    key = {"Authorization": {"contains": f'Token="{JELLYFIN_API_KEY}"'}}
    stubs: list[dict[str, Any]] = [
        {
            "priority": 1,
            "request": {
                "method": "GET",
                "urlPath": "/Items",
                "headers": key,
                "queryParameters": {"parentId": {"equalTo": f"lib-{folder}"}},
            },
            "response": json_response({"Items": items, "TotalRecordCount": len(items)}),
        },
        {
            "priority": 1,
            "request": {
                "method": "POST",
                "urlPath": f"/Items/lib-{folder}/Refresh",
                "headers": key,
            },
            "response": {"status": 204},
        },
    ]
    stubs.append(
        {
            "priority": 1,
            "request": {"method": "GET", "urlPath": "/Users", "headers": key},
            "response": json_response(
                [{"Id": JELLYFIN_ADMIN_ID, "Name": "Admin", "Policy": {"IsAdministrator": True}}]
            ),
        }
    )
    for item in items:
        stubs += [
            {
                # With an API key, Jellyfin reads an item as a user (F26).
                "priority": 1,
                "request": {
                    "method": "GET",
                    "urlPath": f"/Items/{item['Id']}",
                    "headers": key,
                    "queryParameters": {"userId": {"equalTo": JELLYFIN_ADMIN_ID}},
                },
                "response": json_response(item),
            },
            {
                "priority": 1,
                "request": {"method": "POST", "urlPath": f"/Items/{item['Id']}", "headers": key},
                "response": {"status": 204},
            },
        ]
    return stubs


def jellyfin_file_stubs(item_id: str, data: bytes) -> list[dict[str, Any]]:
    """The file of an item of the fake Jellyfin (`GET /Items/{id}/Download`, F39): whole, and
    its first byte alone with its size for `Range: bytes=0-0`."""
    key = {"Authorization": {"contains": f'Token="{JELLYFIN_API_KEY}"'}}
    path = f"/Items/{item_id}/Download"
    headers = {"Content-Type": "application/octet-stream"}
    return [
        {
            # Below the range stub: WireMock takes the first priority that matches (1 first).
            "priority": 2,
            "request": {"method": "GET", "urlPath": path, "headers": key},
            "response": {
                "status": 200,
                "base64Body": base64.b64encode(data).decode(),
                "headers": headers,
            },
        },
        {
            "priority": 1,
            "request": {
                "method": "GET",
                "urlPath": path,
                "headers": {**key, "Range": {"equalTo": "bytes=0-0"}},
            },
            "response": {
                "status": 206,
                "base64Body": base64.b64encode(data[:1]).decode(),
                "headers": {**headers, "Content-Range": f"bytes 0-0/{len(data)}"},
            },
        },
    ]


def wait_for_requests(
    fake_sources: FakeSources, method: str, path: str, *, seconds: float = 30
) -> list[dict[str, Any]]:
    """The requests to `path` the fake received, once there is one; read again without
    sleeping, `seconds` at most."""
    deadline = time.monotonic() + seconds
    found: list[dict[str, Any]] = []
    while time.monotonic() < deadline and not found:
        found = fake_sources.requests(method, path)
    return found


def discord_stub() -> dict[str, Any]:
    """The webhook of Discord the journal posts on: every message taken (`200` and its id)."""
    return {
        "priority": 1,
        "request": {"method": "POST", "urlPath": WEBHOOK_PATH},
        "response": json_response({"id": "1"}),
    }


def payload_of(request: dict[str, Any]) -> dict[str, Any]:
    """The JSON of a message of the webhook: its body, or its part `payload_json`."""
    body = str(request["body"])
    if "payload_json" in body:
        start = body.index("{", body.index("payload_json"))
        body = body[start : body.rindex("}") + 1].split("\r\n--")[0]
    payload: dict[str, Any] = json.loads(body)
    return payload


def wait_for_messages(
    fake_sources: FakeSources, contains: str, *, count: int = 1, seconds: float = 30
) -> list[dict[str, Any]]:
    """The messages posted on the webhook whose body contains `contains`, once there are
    `count` of them (the journal waits for the end of the window of a batch). Read again
    without sleeping, `seconds` at most."""
    deadline = time.monotonic() + seconds
    found: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        payloads = [payload_of(r) for r in fake_sources.requests("POST", WEBHOOK_PATH)]
        found = [p for p in payloads if contains in json.dumps(p, ensure_ascii=False)]
        if len(found) >= count:
            return found
    return found


def new_request_id() -> str:
    """A unique X-Request-ID: the records of a request are found by it."""
    return uuid.uuid4().hex


def run_search(client: httpx.Client, body: dict[str, Any]) -> dict[str, Any]:
    """Start a release search, follow its events to their end, and read its releases."""
    started = client.post("/api/v1/searches", json=body)
    started.raise_for_status()
    search_id = started.json()["id"]
    events(client, search_id)
    found = client.get(f"/api/v1/searches/{search_id}")
    found.raise_for_status()
    result: dict[str, Any] = found.json()
    return result


def events(client: httpx.Client, search_id: str) -> list[tuple[str, dict[str, Any]]]:
    """The Server-Sent Events of a search, until its `end` event: (name, data)."""
    found: list[tuple[str, dict[str, Any]]] = []
    with client.stream("GET", f"/api/v1/searches/{search_id}/events", timeout=90.0) as response:
        response.raise_for_status()
        name = ""
        for line in response.iter_lines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                found.append((name, json.loads(line.removeprefix("data: "))))
                if name == "end":
                    break
    return found


def send_completed(
    client: httpx.Client,
    fake_sources: FakeSources,
    *,
    name: str,
    kind: str,
    content_path: str,
    volumes: dict[str, Any],
    author: str,
    title: str | None = None,
) -> tuple[dict[str, Any], str]:
    """A release of the work `name` searched, sent, then complete in qBittorrent, its files at
    `content_path`: the placement worker takes it from there. The download and its hash."""
    from shelfdrop.utils.torrent import torrent_id
    from tests.unit.support import torrent_file

    categories = {"manga": [7030], "ebook": [7020], "audiobook": [3030]}[kind]
    link = name.lower().replace(" ", "-")
    data = torrent_file(name)
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_search_stub(
                name,
                categories,
                [
                    prowlarr_release(
                        f"https://nyaa.test/view/{link}",
                        title or f"{name.replace(' ', '.')}.FRENCH",
                        link,
                    )
                ],
            ),
            prowlarr_download_stub(1, link, data),
            *torrent_stubs(
                digest,
                name,
                complete={"state": "stalledUP", "progress": 1.0, "content_path": content_path},
            ),
        ]
    )
    search = run_search(client, {"mode": "work", "kind": kind, "title": name, "names": [name]})
    sent = client.post(
        "/api/v1/downloads",
        json={
            "search_id": search["progress"]["id"],
            "work_id": None,
            "author": author,
            "series": name,
            "releases": [{"id": search["releases"][0]["id"], "volumes": volumes}],
        },
    )
    assert sent.status_code == 200, sent.text
    download: dict[str, Any] = sent.json()["downloads"][0]
    wait_for_download(client, download["id"], lambda d: d["progress"]["state"] != "waiting")
    fake_sources.post(f"/tests/complete/{digest}")
    return download, digest
