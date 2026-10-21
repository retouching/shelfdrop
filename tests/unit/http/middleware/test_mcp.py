"""shelfdrop.http.middleware.mcp: the MCP server behind an access token."""

from typing import Any

import httpx
import pytest
from starlette.types import Receive, Scope, Send

from shelfdrop.http.middleware.mcp import HOLDER_STATE, McpMiddleware
from shelfdrop.tokens.exceptions import TokenRefusedError, TokenThrottledError
from shelfdrop.tokens.types import StoredToken

HERMES = StoredToken(id=1, name="Hermes", scope="write", expires_at=None, last_used_at=None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class Recorder:
    """An ASGI app that answers 200 and keeps the scopes it received."""

    def __init__(self) -> None:
        self.scopes: list[Scope] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.scopes.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


async def check(secret: str) -> StoredToken:
    if secret == "sd_busy":
        raise TokenThrottledError
    if secret != "sd_hermes":
        raise TokenRefusedError
    return HERMES


def client_for(server: Recorder, app: Recorder) -> httpx.AsyncClient:
    middleware = McpMiddleware(app, path="/mcp", server=server, check=check)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=middleware), base_url="http://t")


@pytest.mark.anyio
async def test_a_token_reaches_the_server_with_its_holder() -> None:
    server, app = Recorder(), Recorder()

    async with client_for(server, app) as client:
        response = await client.post("/mcp", headers={"Authorization": "Bearer sd_hermes"})

    assert response.status_code == 200
    state: dict[str, Any] = server.scopes[0]["state"]
    assert state[HOLDER_STATE] == HERMES
    assert app.scopes == []


@pytest.mark.anyio
@pytest.mark.parametrize("header", [None, "Bearer sd_unknown", "Bearer ", "Basic dTpw"])
async def test_without_a_valid_token_the_server_answers_401(header: str | None) -> None:
    server, app = Recorder(), Recorder()
    headers = {} if header is None else {"Authorization": header}

    async with client_for(server, app) as client:
        client.cookies.set("__Host-shelfdrop", "a-session")
        response = await client.post("/mcp", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"code": "not_signed_in", "detail": "Not signed in", "data": None}
    assert response.headers["www-authenticate"] == "Bearer"
    assert server.scopes == []


@pytest.mark.anyio
async def test_a_token_too_busy_gets_429() -> None:
    server, app = Recorder(), Recorder()

    async with client_for(server, app) as client:
        response = await client.post("/mcp", headers={"Authorization": "Bearer sd_busy"})

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"


@pytest.mark.anyio
async def test_the_other_paths_go_to_the_application() -> None:
    server, app = Recorder(), Recorder()

    async with client_for(server, app) as client:
        await client.get("/mcp/other")
        await client.get("/api/v1/downloads")

    assert [s["path"] for s in app.scopes] == ["/mcp/other", "/api/v1/downloads"]
    assert server.scopes == []
