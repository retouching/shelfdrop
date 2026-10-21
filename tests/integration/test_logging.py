"""The logs of the real API: JSON records tied to their request, never a query string nor an
address of a source."""

import httpx
import pytest

from tests.integration.support import Stack, new_request_id

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
    """MyAnimeList (Jikan) failed when Chainsaw Man was recorded: its record names the source
    and the class of the failure, never the address nor the answer."""
    request_id = new_request_id()
    client.get(
        "/api/v1/works",
        params={"q": "Chainsaw Man", "kind": "manga"},
        headers={"X-Request-ID": request_id},
    )

    records = [
        r
        for r in stack.log_records(request_id, expected=3)
        if r["message"] == "Metadata source unavailable"
    ]

    assert {r["source"] for r in records} >= {"myanimelist", "anilist"}
    assert {r["error"] for r in records} == {"SourceError"}
    logs = stack.api_logs()
    assert "jikan" not in logs
    assert "fake-sources" not in logs
