"""Writes of the API come from its own pages alone: a POST, PUT, PATCH or DELETE under the
prefix of the API needs an `Origin` header that names the host of the request (`Host`), or it
gets a 403 `origin_refused`. Browsers send `Origin` with every such request; the session cookie
is SameSite=Strict on top of it."""

from typing import Final
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from shelfdrop.http.errors.responses import error_response
from shelfdrop.http.errors.types import ErrorCode

WRITES: Final = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def same_host(origin: str | None, host: str | None) -> bool:
    if not origin or not host or origin == "null":
        return False
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and parts.netloc.lower() == host.lower()


class OriginMiddleware:
    def __init__(self, app: ASGIApp, *, api_paths: tuple[str, ...]) -> None:
        self.app = app
        self.api_paths = api_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in WRITES
            and str(scope["path"]).startswith(self.api_paths)
        ):
            headers = Headers(scope=scope)
            if not same_host(headers.get("origin"), headers.get("host")):
                response = error_response(403, ErrorCode.ORIGIN_REFUSED, "Origin refused")
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
