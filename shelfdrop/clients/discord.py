"""Discord: a message posted on the webhook of the journal (`POST <webhook>?wait=true`).

The address of a webhook holds its token: it is never logged, and an error names a status or a
class alone.
"""

import json
from typing import Any, Final

import httpx

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError

# Discord answers `429` with the seconds to wait in its body (`retry_after`) and its headers.
DEFAULT_RETRY_SECONDS: Final = 2.0


class RateLimitedError(ServiceError):
    """Discord asks to wait `retry_after` seconds before the next message of this webhook."""

    def __init__(self, retry_after: float) -> None:
        super().__init__("HTTP 429", status=429)
        self.retry_after = retry_after


def retry_after_of(response: httpx.Response) -> float:
    try:
        body = response.json()
    except ValueError:
        body = None
    value = body.get("retry_after") if isinstance(body, dict) else None
    if isinstance(value, int | float) and not isinstance(value, bool) and value >= 0:
        return float(value)
    header = response.headers.get("Retry-After")
    try:
        return float(header) if header is not None else DEFAULT_RETRY_SECONDS
    except ValueError:
        return DEFAULT_RETRY_SECONDS


class DiscordClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def post(
        self,
        webhook: str | None,
        payload: dict[str, Any],
        attachment: tuple[str, bytes, str] | None = None,
    ) -> None:
        """A message (`content`, `embeds`...), with a file named in its embeds as
        `attachment://<name>` when `attachment` (name, bytes, type) is given. Raises
        RateLimitedError (429), ServiceError."""
        if not webhook:
            raise ServiceNotConfiguredError("no webhook")
        try:
            if attachment is None:
                response = await self.http.post(webhook, params={"wait": "true"}, json=payload)
            else:
                name, data, content_type = attachment
                response = await self.http.post(
                    webhook,
                    params={"wait": "true"},
                    files={
                        "payload_json": (None, json.dumps(payload), "application/json"),
                        "files[0]": (name, data, content_type),
                    },
                )
        except httpx.HTTPError as exc:
            raise ServiceError(type(exc).__name__) from exc
        if response.status_code == 429:
            raise RateLimitedError(retry_after_of(response))
        if response.status_code not in (200, 204):
            raise ServiceError(f"HTTP {response.status_code}", status=response.status_code)
