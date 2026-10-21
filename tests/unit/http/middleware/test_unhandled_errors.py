import asyncio
import json
import logging

import pytest
from starlette.requests import ClientDisconnect
from starlette.types import Message, Receive, Scope, Send

from shelfdrop.http.middleware.unhandled_errors import UnhandledErrorsMiddleware
from tests.unit.http.middleware.support import call_asgi, http_scope

LOGGER = "shelfdrop.http.middleware.unhandled_errors"


class FatalError(BaseException):
    """Stands for cancellation-like exceptions, which must never be swallowed."""


def test_exception_before_the_response_becomes_a_logged_json_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def failing(scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError("secret-in-message")

    sent: list[Message] = []
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        asyncio.run(call_asgi(UnhandledErrorsMiddleware(failing), http_scope(), sent))

    start, body = sent
    assert start["status"] == 500
    assert (b"content-type", b"application/json") in start["headers"]
    assert json.loads(body["body"]) == {
        "code": "internal_error",
        "detail": "Internal Server Error",
        "data": None,
    }
    assert b"secret-in-message" not in body["body"]
    [record] = [record for record in caplog.records if record.name == LOGGER]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.exc_info[0] is RuntimeError


def test_exception_after_the_response_started_propagates() -> None:
    async def failing_midway(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("midway")

    sent: list[Message] = []
    with pytest.raises(RuntimeError, match="midway"):
        asyncio.run(call_asgi(UnhandledErrorsMiddleware(failing_midway), http_scope(), sent))

    assert [message["status"] for message in sent] == [200]


def test_base_exceptions_are_never_caught() -> None:
    async def fatal(scope: Scope, receive: Receive, send: Send) -> None:
        raise FatalError

    sent: list[Message] = []
    with pytest.raises(FatalError):
        asyncio.run(call_asgi(UnhandledErrorsMiddleware(fatal), http_scope(), sent))

    assert sent == []


def test_a_client_gone_is_no_error_and_goes_on_unlogged(caplog: pytest.LogCaptureFixture) -> None:
    async def cut(scope: Scope, receive: Receive, send: Send) -> None:
        raise ClientDisconnect

    sent: list[Message] = []
    with caplog.at_level(logging.DEBUG, logger=LOGGER), pytest.raises(ClientDisconnect):
        asyncio.run(call_asgi(UnhandledErrorsMiddleware(cut), http_scope(), sent))

    assert sent == []
    assert [record for record in caplog.records if record.name == LOGGER] == []
