"""The logs of the real API: JSON records tied to their request, never a query string nor an
address of a source; the records of the API and of the placement worker read back by the route
of the page, for a session alone (ADR 0023)."""

from typing import Any

import httpx
import pytest

from tests.integration.support import (
    LOG_READ_ATTEMPTS,
    Stack,
    bearer,
    new_access_token,
    new_request_id,
)

pytestmark = [pytest.mark.security, pytest.mark.security_logging]

ACCESS_LOGGER = "shelfdrop.http.middleware.access_log"


def test_a_request_has_one_access_record(stack: Stack, client: httpx.Client) -> None:
    request_id = new_request_id()
    client.get("/api/v1/nothing", headers={"X-Request-ID": request_id})

    records = [r for r in stack.log_records(request_id, expected=1) if r["logger"] == ACCESS_LOGGER]

    assert len(records) == 1
    record = records[0]
    assert record["method"] == "GET"
    assert record["path"] == "/api/v1/nothing"
    assert record["status"] == 404
    assert record["level"] == "INFO"
    assert isinstance(record["duration_ms"], float)


def test_the_query_string_is_never_logged(stack: Stack, client: httpx.Client) -> None:
    request_id = new_request_id()
    marker = "marker-of-the-query-91c2"
    client.get(
        "/api/v1/works", params={"q": "a", "kind": marker}, headers={"X-Request-ID": request_id}
    )

    stack.log_records(request_id, expected=1)

    assert marker not in stack.api_logs()


def test_a_failed_source_logs_its_name_and_a_class(stack: Stack, client: httpx.Client) -> None:
    """AniList refused when Chainsaw Man was recorded: its record names the source and the class
    of the failure, never the address nor the answer."""
    request_id = new_request_id()
    client.get(
        "/api/v1/works",
        params={"q": "Chainsaw Man", "kind": "manga"},
        headers={"X-Request-ID": request_id},
    )

    records = [
        r
        for r in stack.log_records(request_id, expected=2)
        if r["message"] == "Metadata source unavailable"
    ]

    assert {r["source"] for r in records} == {"anilist"}
    assert {r["error"] for r in records} == {"SourceError"}
    logs = stack.api_logs()
    assert "graphql.anilist.co" not in logs
    assert "fake-sources" not in logs


def read_logs(client: httpx.Client, params: dict[str, str]) -> list[dict[str, Any]]:
    """The entries the route gives, read again (no sleep) until one is there: a record written
    just after the response of its request may not be in the file yet."""
    entries: list[dict[str, Any]] = []
    for _ in range(LOG_READ_ATTEMPTS):
        response = client.get("/api/v1/logs", params=params)
        assert response.status_code == 200, response.text
        entries = response.json()["entries"]
        if entries:
            break
    return entries


def test_the_route_reads_the_access_record_of_a_request(client: httpx.Client) -> None:
    request_id = new_request_id()
    client.get("/api/v1/nothing", params={"q": "hidden"}, headers={"X-Request-ID": request_id})

    entries = [
        entry
        for entry in read_logs(client, {"text": request_id, "level": "INFO"})
        if entry["logger"] == ACCESS_LOGGER
    ]

    assert len(entries) == 1
    entry = entries[0]
    assert entry["request_id"] == request_id
    assert entry["level"] == "INFO"
    assert entry["fields"]["path"] == "/api/v1/nothing"
    assert entry["fields"]["status"] == 404
    assert "hidden" not in str(entry)


def test_the_route_reads_the_records_of_the_placement_worker(client: httpx.Client) -> None:
    entries = read_logs(client, {"service": "placement", "text": "Placement worker started"})

    assert entries
    assert entries[0]["logger"] == "shelfdrop.placement.worker"


def test_a_read_of_the_logs_is_never_logged_at_info(stack: Stack, client: httpx.Client) -> None:
    """The page reads them every few seconds: its reads stay out of the logs, and so does the
    text searched."""
    request_id = new_request_id()
    marker = "marker-of-the-logs-5e1a"
    response = client.get(
        "/api/v1/logs", params={"text": marker}, headers={"X-Request-ID": request_id}
    )

    assert response.status_code == 200
    assert response.json() == {"entries": [], "next": None}
    assert stack.log_records(request_id, expected=0) == []
    assert marker not in stack.api_logs()


def test_the_logs_are_kept_for_a_session(client: httpx.Client, anonymous: httpx.Client) -> None:
    token = new_access_token(client, "write", name="Journaux")

    with_token = anonymous.get("/api/v1/logs", headers=bearer(token["secret"]))
    without = anonymous.get("/api/v1/logs")

    assert with_token.status_code == 403
    assert with_token.json()["code"] == "token_forbidden"
    assert without.status_code == 401
    assert without.json()["code"] == "not_signed_in"
