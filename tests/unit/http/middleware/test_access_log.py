import asyncio
import logging

import pytest
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Receive, Scope, Send

from shelfdrop.http.middleware.access_log import AccessLogMiddleware
from tests.unit.http.middleware.support import call_asgi, http_scope, plain_app

LOGGER = "shelfdrop.http.middleware.access_log"
QUIET_PATHS = frozenset({"/health", "/api/v1/agent/sync"})


def call(app: ASGIApp, scope: Scope) -> None:
    asyncio.run(call_asgi(AccessLogMiddleware(app, quiet_paths=QUIET_PATHS), scope, []))


def single_record(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    [record] = [record for record in caplog.records if record.name == LOGGER]
    return record


def test_logs_one_structured_record_without_query_string_nor_headers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    scope = http_scope(
        "/items",
        query_string=b"api_key=query-secret",
        headers=[(b"authorization", b"Bearer header-secret")],
    )

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        call(plain_app(404), scope)

    record = single_record(caplog)
    fields = vars(record)
    assert record.levelno == logging.INFO
    assert record.getMessage().startswith("GET /items 404 ")
    assert fields["method"] == "GET"
    assert fields["path"] == "/items"
    assert fields["status"] == 404
    assert fields["duration_ms"] >= 0
    assert fields["client_ip"] == "192.0.2.10"
    assert "query-secret" not in str(fields)
    assert "header-secret" not in str(fields)


@pytest.mark.parametrize(
    ("path", "status", "level"),
    [
        ("/health", 200, logging.DEBUG),
        ("/health", 500, logging.INFO),
        ("/items", 200, logging.INFO),
        ("/api/v1/agent/sync", 200, logging.DEBUG),
        ("/api/v1/agent/sync", 401, logging.INFO),
        ("/v1/agent/sync", 200, logging.INFO),
    ],
    ids=["health-ok", "health-error", "other-path", "sync-ok", "sync-refused", "sync-unprefixed"],
)
def test_only_successful_polls_are_logged_at_debug(
    caplog: pytest.LogCaptureFixture, path: str, status: int, level: int
) -> None:
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        call(plain_app(status), http_scope(path))

    assert single_record(caplog).levelno == level


def test_exception_before_the_response_is_logged_as_500_and_propagates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def failing(scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError("boom")

    with caplog.at_level(logging.DEBUG, logger=LOGGER), pytest.raises(RuntimeError, match="boom"):
        call(failing, http_scope())

    assert vars(single_record(caplog))["status"] == 500


def test_a_client_gone_before_the_response_is_logged_as_499_without_a_trace(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def cut(scope: Scope, receive: Receive, send: Send) -> None:
        raise ClientDisconnect

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        call(cut, http_scope())

    record = single_record(caplog)
    assert (record.levelno, vars(record)["status"], record.exc_info) == (logging.INFO, 499, None)


def test_a_client_gone_after_the_response_started_keeps_its_status(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def cut_midway(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise ClientDisconnect

    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        call(cut_midway, http_scope())

    assert vars(single_record(caplog))["status"] == 200
