"""One access log record per HTTP request (replaces uvicorn's access log)."""

import logging
import time
from typing import Final

from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

# The status of a request whose client went away while its body was read (as proxies log it):
# nobody waits for an answer, so none is sent.
CLIENT_CLOSED_REQUEST: Final = 499


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp, *, quiet_paths: frozenset[str]) -> None:
        self.app = app
        # Paths polled every few seconds (the Compose healthcheck): their
        # successes are logged at DEBUG only.
        self.quiet_paths = quiet_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        # Stays 500 when the application raises before starting a response.
        status_code = 500
        response_started = False

        async def send_capturing_status(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_capturing_status)
        except ClientDisconnect:
            # An upload cut by its client: an expected end, logged without a trace. Returning
            # without a response is silent in uvicorn once the client is gone.
            if not response_started:
                status_code = CLIENT_CLOSED_REQUEST
        finally:
            log_access(scope, status_code, time.perf_counter() - started, self.quiet_paths)


def log_access(
    scope: Scope, status_code: int, elapsed_seconds: float, quiet_paths: frozenset[str]
) -> None:
    method: str = scope["method"]
    # Never the query string nor any header: they may carry credentials.
    path: str = scope["path"]
    duration_ms = round(elapsed_seconds * 1000, 1)
    client = scope.get("client")
    level = logging.DEBUG if path in quiet_paths and status_code < 400 else logging.INFO
    logger.log(
        level,
        "%s %s %d %.1fms",
        method,
        path,
        status_code,
        duration_ms,
        extra={
            "method": method,
            "path": path,
            "status": status_code,
            "duration_ms": duration_ms,
            "client_ip": client[0] if client else None,
        },
    )
