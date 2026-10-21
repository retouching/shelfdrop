"""RedirectTransport: every request of the metadata clients sent to one origin, for the test stack
alone (`Settings.sources_origin`, ADR 0010)."""

from typing import Final, override

import httpx

ORIGINAL_ORIGIN: Final = "X-Original-Origin"


class RedirectTransport(httpx.AsyncBaseTransport):
    """Sends a request to `origin` with the same path, query and body; the origin it was meant
    for goes in the header X-Original-Origin."""

    def __init__(self, origin: str, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self.origin = httpx.URL(origin)
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0)

    @override
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        request.headers[ORIGINAL_ORIGIN] = f"{url.scheme}://{url.netloc.decode('ascii')}"
        request.url = url.copy_with(
            scheme=self.origin.scheme, host=self.origin.host, port=self.origin.port
        )
        request.headers["Host"] = self.origin.netloc.decode("ascii")
        return await self.inner.handle_async_request(request)

    @override
    async def aclose(self) -> None:
        await self.inner.aclose()
