"""The MCP server at its path (ADR 0022), behind an access token: `Authorization: Bearer <secret>`
checked like a request of the API (unknown, expired, revoked: 401 `not_signed_in`; 60 requests a
minute: 429 `too_many_requests`), the token kept in the scope for the tools. The session cookie
is never read there."""

from collections.abc import Awaitable, Callable
from typing import Final

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from shelfdrop.http.dependencies import bearer_of
from shelfdrop.http.errors.responses import error_response
from shelfdrop.http.errors.types import ErrorCode
from shelfdrop.tokens.exceptions import TokenRefusedError, TokenThrottledError
from shelfdrop.tokens.types import StoredToken

# The key of the token checked in `scope["state"]`, read by the tools.
HOLDER_STATE: Final = "shelfdrop.holder"
CHALLENGE: Final = {"WWW-Authenticate": "Bearer"}


class McpMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        path: str,
        server: ASGIApp,
        check: Callable[[str], Awaitable[StoredToken]],
    ) -> None:
        self.app = app
        self.path = path
        self.server = server
        self.check = check

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != self.path:
            await self.app(scope, receive, send)
            return
        secret = bearer_of(Request(scope))
        try:
            if not secret:
                raise TokenRefusedError
            token = await self.check(secret)
        except TokenRefusedError:
            response = error_response(
                401, ErrorCode.NOT_SIGNED_IN, "Not signed in", headers=CHALLENGE
            )
            await response(scope, receive, send)
            return
        except TokenThrottledError:
            response = error_response(429, ErrorCode.TOO_MANY_REQUESTS, "Too many requests")
            await response(scope, receive, send)
            return
        scope.setdefault("state", {})[HOLDER_STATE] = token
        await self.server(scope, receive, send)
