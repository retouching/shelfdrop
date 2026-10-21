import asyncio

from starlette.types import Message, Receive, Scope, Send

from shelfdrop.http.middleware.request_id import RequestIdMiddleware
from shelfdrop.logging.context import request_id_var
from tests.unit.http.middleware.support import call_asgi, http_scope


def run(headers: list[tuple[bytes, bytes]]) -> tuple[str | None, str | None, str]:
    """(request id seen by the app, request id after the call, X-Request-ID sent back)."""
    seen: list[str | None] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(request_id_var.get())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def scenario() -> tuple[str | None, list[Message]]:
        sent: list[Message] = []
        await call_asgi(RequestIdMiddleware(app), http_scope(headers=headers), sent)
        return request_id_var.get(), sent

    after, sent = asyncio.run(scenario())
    response_headers = dict(sent[0]["headers"])
    return seen[0], after, response_headers[b"x-request-id"].decode()


def test_echoed_request_id_is_the_log_context_during_the_call_only() -> None:
    seen, after, header = run([(b"x-request-id", b"job-42")])

    assert seen == "job-42"
    assert header == "job-42"
    assert after is None


def test_generated_request_id_is_the_log_context() -> None:
    seen, _, header = run([])

    assert seen == header
