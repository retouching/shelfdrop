"""What the integration tests share: the Compose project of the test stack, its logs, and the fake
metadata sources that replay the recorded exchanges of `tests/unit/works/fixtures/`."""

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qsl, urlsplit

import httpx

PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
COMPOSE_FILES: Final = ("docker/compose.yaml", "docker/compose.test.yaml")
FIXTURES: Final = PROJECT_ROOT / "tests" / "unit" / "works" / "fixtures"
UP_TIMEOUT_SECONDS: Final = 900
COMMAND_TIMEOUT_SECONDS: Final = 120
LOG_READ_ATTEMPTS: Final = 20
# Every variable docker/compose.yaml requires, given to every Compose call: the stack never
# reads the .env of the developer.
STACK_ENVIRONMENT: Final = {"SHELFDROP_CONTACT": "tests@shelfdrop.invalid"}
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

    def unmatched(self) -> list[str]:
        """The requests no stub answered: method, original origin and URL."""
        response = httpx.get(f"{self.url}/__admin/requests/unmatched", timeout=10.0)
        response.raise_for_status()
        found: list[str] = []
        for request in response.json()["requests"]:
            headers = request.get("headers", {})
            found.append(f"{request['method']} {headers.get(ORIGINAL_ORIGIN)}{request['url']}")
        return found

    def reset_journal(self) -> None:
        httpx.delete(f"{self.url}/__admin/requests", timeout=10.0).raise_for_status()


def new_request_id() -> str:
    """A unique X-Request-ID: the records of a request are found by it."""
    return uuid.uuid4().hex
