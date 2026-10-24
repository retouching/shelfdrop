"""The set-up of the first launch (ADR 0024): while it is not finished, every request under
the paths guarded (the API, the MCP server) answers 409 `setup_required`, but those under the
paths left open (the set-up, the session, the settings). /health and the pages stay outside."""

from collections.abc import Awaitable, Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from shelfdrop.http.errors.responses import error_response
from shelfdrop.http.errors.types import ErrorCode


class SetupMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        guarded: tuple[str, ...],
        open_paths: tuple[str, ...],
        needed: Callable[[], Awaitable[bool]],
    ) -> None:
        self.app = app
        self.guarded = guarded
        self.open_paths = open_paths
        self.needed = needed

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope["path"] if scope["type"] == "http" else ""
        if (
            path
            and any(path == p or path.startswith(f"{p}/") for p in self.guarded)
            and not any(path == p or path.startswith(f"{p}/") for p in self.open_paths)
            and await self.needed()
        ):
            response = error_response(409, ErrorCode.SETUP_REQUIRED, "Setup required")
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
