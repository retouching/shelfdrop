"""Drive a pure ASGI middleware without a server."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


def http_scope(
    path: str = "/items",
    *,
    query_string: bytes = b"",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": query_string,
        "headers": headers if headers is not None else [],
        "client": ("192.0.2.10", 50000),
        "server": ("testserver", 80),
        "state": {},
    }


def plain_app(status: int = 200) -> ASGIApp:
    """An application answering `status` with an empty body."""

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return app


async def call_asgi(app: ASGIApp, scope: Scope, sent: list[Message]) -> None:
    """Call `app` once; every message it sends is appended to `sent`, even if it raises."""

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    await app(scope, receive, send)
