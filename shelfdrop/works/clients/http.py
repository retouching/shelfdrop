"""The requests of the metadata clients: one answer read as JSON or text, any failure turned
into a SourceError."""

from typing import Any

import httpx

from shelfdrop.works.exceptions import SourceError


async def get_json(
    http: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    try:
        response = await http.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise SourceError(type(exc).__name__) from exc
    return decode_json(response)


async def post_json(http: httpx.AsyncClient, url: str, body: dict[str, Any]) -> Any:
    try:
        response = await http.post(url, json=body)
    except httpx.HTTPError as exc:
        raise SourceError(type(exc).__name__) from exc
    return decode_json(response)


async def get_text(
    http: httpx.AsyncClient, url: str, *, params: dict[str, str | int] | None = None
) -> str:
    try:
        response = await http.get(url, params=params)
    except httpx.HTTPError as exc:
        raise SourceError(type(exc).__name__) from exc
    if response.status_code != 200:
        raise SourceError(f"HTTP {response.status_code}")
    return response.text


def decode_json(response: httpx.Response) -> Any:
    if response.status_code != 200:
        raise SourceError(f"HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError("invalid JSON") from exc


def year_of(value: object) -> int | None:
    """First 4 digits of a date-like value ('2018-12-03', 2018, '2018')."""
    text = str(value or "")[:4]
    return int(text) if text.isdigit() else None
