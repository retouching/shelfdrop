"""Innermost middleware: an unhandled exception becomes a logged, JSON 500 internal_error."""

import logging

from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shelfdrop.http.errors.responses import internal_error_response

logger = logging.getLogger(__name__)


class UnhandledErrorsMiddleware:
    """Inside the other middlewares, so the 500 still gets the request id and security headers.

    Only Exception is caught, never cancellation. Once the response has started the exception
    is re-raised: uvicorn logs it and closes the connection. `ClientDisconnect` (the client went
    away while its body was read) is no error: it goes on to AccessLogMiddleware, which logs 499.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def send_tracking_start(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking_start)
        except ClientDisconnect:
            raise
        except Exception:
            if response_started:
                raise
            logger.exception("Unhandled exception")
            response = internal_error_response()
            await response(scope, receive, send)
