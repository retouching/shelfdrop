"""shelfdrop.http.middleware.setup: before the end of the set-up, the API answers its routes
alone."""

import json

import pytest
from starlette.types import Message

from shelfdrop.http.middleware.setup import SetupMiddleware
from tests.unit.http.middleware.support import call_asgi, http_scope, plain_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def middleware(*, needed: bool, asked: list[str]) -> SetupMiddleware:
    async def check() -> bool:
        asked.append("asked")
        return needed

    return SetupMiddleware(
        plain_app(),
        guarded=("/api", "/mcp"),
        open_paths=("/api/v1/setup", "/api/v1/session", "/api/v1/settings"),
        needed=check,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/api/v1/works", "/api/v1/tokens", "/api/docs", "/mcp"])
async def test_a_route_of_the_api_waits_for_the_end_of_the_set_up(path: str) -> None:
    sent: list[Message] = []

    await call_asgi(middleware(needed=True, asked=[]), http_scope(path), sent)

    assert sent[0]["status"] == 409
    body = json.loads(sent[1]["body"])
    assert body == {"code": "setup_required", "detail": "Setup required", "data": None}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/setup",
        "/api/v1/setup/account",
        "/api/v1/session",
        "/api/v1/settings/test",
        "/health",
        "/",
        "/settings",
        "/assets/app.js",
        "/api/v1/settingsx",
    ],
)
async def test_the_set_up_the_session_the_settings_and_the_pages_stay_open(path: str) -> None:
    sent: list[Message] = []
    asked: list[str] = []

    await call_asgi(middleware(needed=True, asked=asked), http_scope(path), sent)

    if path == "/api/v1/settingsx":
        assert sent[0]["status"] == 409
    else:
        assert sent[0]["status"] == 200
        assert asked == []


@pytest.mark.anyio
async def test_once_the_set_up_is_done_everything_goes_through() -> None:
    sent: list[Message] = []

    await call_asgi(middleware(needed=False, asked=[]), http_scope("/api/v1/works"), sent)

    assert sent[0]["status"] == 200
