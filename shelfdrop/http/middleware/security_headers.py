"""Security headers on every response (OWASP); a route may set its own value first.

The API answers are never cached and load nothing. The pages of the front-end load their
scripts, styles, fonts and images from the same origin alone; so does the page of the API
document (Swagger UI, ADR 0021), which also asks the API itself and is never cached.
"""

from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADERS: Final = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
)
API_CONTENT_SECURITY_POLICY: Final = "default-src 'none'; frame-ancestors 'none'"
PAGE_CONTENT_SECURITY_POLICY: Final = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data: https:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
DOCS_CONTENT_SECURITY_POLICY: Final = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, api_paths: tuple[str, ...], docs_path: str) -> None:
        self.app = app
        # Prefixes of the paths answered by the API rather than by the pages.
        self.api_paths = api_paths
        # The page of the API document, under the API.
        self.docs_path = docs_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        api = path.startswith(self.api_paths)
        policy = DOCS_CONTENT_SECURITY_POLICY if path == self.docs_path else None

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in HEADERS:
                    headers.setdefault(name, value)
                if api:
                    headers.setdefault("Cache-Control", "no-store")
                    headers.setdefault(
                        "Content-Security-Policy", policy or API_CONTENT_SECURITY_POLICY
                    )
                else:
                    headers.setdefault("Content-Security-Policy", PAGE_CONTENT_SECURITY_POLICY)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
