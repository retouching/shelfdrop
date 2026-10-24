"""The MCP server through the real image: a real MCP client over Streamable
HTTP with an access token finds a work, the releases of the fake Prowlarr, sends one to the fake
qBittorrent under the name of its token, and reads the downloads and Ranger; a token of reading
cannot send; no token, or one revoked, gets 401."""

from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.types import CallToolResult

from shelfdrop.utils.torrent import torrent_id
from tests.integration.support import (
    FakeSources,
    Stack,
    bearer,
    new_access_token,
    prowlarr_download_stub,
    prowlarr_release,
    prowlarr_search_stub,
    torrent_stubs,
    wait_for_download,
)
from tests.unit.support import torrent_file

pytestmark = [pytest.mark.access, pytest.mark.access_mcp]

TOOLS = [
    "search_works",
    "search_releases",
    "grab_releases",
    "list_downloads",
    "retry_download",
    "list_files_to_place",
    "place_file",
]

type Steps[T] = Callable[[ClientSession], Awaitable[T]]


def with_mcp[T](stack: Stack, secret: str, steps: Steps[T]) -> T:
    """Run `steps` on a session of the MCP server of the stack, with the token `secret`."""

    async def run() -> T:
        async with (
            create_mcp_http_client(headers=bearer(secret)) as http,
            streamable_http_client(f"{stack.base_url}/mcp", http_client=http) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            return await steps(session)

    return anyio.run(run)


def structured(result: CallToolResult) -> dict[str, Any]:
    assert not result.is_error, result.content
    found: dict[str, Any] = result.structured_content
    return found


@pytest.mark.usefixtures("qbittorrent_saved")
def test_a_token_finds_a_work_its_releases_and_sends_one_under_its_name(
    stack: Stack, client: httpx.Client, fake_sources: FakeSources
) -> None:
    name = "Shelfdrop Mcp Test"
    title = "Shelfdrop.Mcp.Test.T01-T03.FRENCH.CBZ.eBook-PapriKa+"
    data = torrent_file("Shelfdrop Mcp Test T01-T03")
    digest = torrent_id(data)
    assert digest is not None
    fake_sources.load(
        [
            prowlarr_search_stub(
                name, [7030], [prowlarr_release("https://nyaa.test/view/9301", title, "mcp-1")]
            ),
            prowlarr_download_stub(1, "mcp-1", data),
            *torrent_stubs(digest, "Shelfdrop Mcp Test T01-T03"),
        ]
    )
    secret = new_access_token(client, "write", "Hermes")["secret"]

    async def steps(
        session: ClientSession,
    ) -> tuple[
        list[str], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
    ]:
        tools = [tool.name for tool in (await session.list_tools()).tools]
        works = structured(
            await session.call_tool("search_works", {"query": "Chainsaw Man", "kind": "manga"})
        )
        search = structured(
            await session.call_tool(
                "search_releases", {"kind": "manga", "title": name, "names": [name]}
            )
        )
        release = search["releases"][0]
        sent = structured(
            await session.call_tool(
                "grab_releases",
                {
                    "search_id": search["progress"]["id"],
                    "work_id": "mangaupdates:9301",
                    "author": "Tatsuki Fujimoto",
                    "series": name,
                    "releases": [
                        {"id": release["id"], "volumes": {"kind": "range", "first": 1, "last": 3}}
                    ],
                },
            )
        )
        downloads = structured(await session.call_tool("list_downloads", {}))
        files = structured(await session.call_tool("list_files_to_place", {}))
        return tools, works, search, sent, downloads, files

    tools, works, search, sent, downloads, files = with_mcp(stack, secret, steps)

    assert tools == TOOLS
    assert any("Chainsaw Man" in work["title"] for work in works["works"])
    assert [r["title"] for r in search["releases"]] == [title]
    created = sent["downloads"][0]
    assert created["created_by"] == "Hermes"
    assert created["series"] == name
    assert created["id"] in [d["id"] for d in downloads["downloads"]]
    assert "items" in files
    found = wait_for_download(client, created["id"], lambda d: d["progress"]["state"] != "waiting")
    assert found["info_hash"] == digest
    assert found["created_by"] == "Hermes"


def test_a_token_of_reading_reads_and_never_sends(stack: Stack, client: httpx.Client) -> None:
    secret = new_access_token(client, "read", "Grafana")["secret"]

    async def steps(
        session: ClientSession,
    ) -> tuple[CallToolResult, CallToolResult, CallToolResult]:
        downloads = await session.call_tool("list_downloads", {})
        grab = await session.call_tool(
            "grab_releases",
            {
                "search_id": "x",
                "releases": [{"id": "0123456789abcdef", "volumes": {"kind": "single", "first": 1}}],
            },
        )
        retry = await session.call_tool("retry_download", {"download_id": 1})
        return downloads, grab, retry

    downloads, grab, retry = with_mcp(stack, secret, steps)

    assert not downloads.is_error
    assert grab.is_error
    assert "token_forbidden" in str(grab.content)
    assert retry.is_error
    assert "token_forbidden" in str(retry.content)


INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
ACCEPT = {"Accept": "application/json, text/event-stream"}


@pytest.mark.parametrize("header", [None, "Bearer sd_made-up", "Basic dXNlcjpwYXNz"])
def test_without_a_valid_token_the_server_answers_401(
    stack: Stack, signed_in: dict[str, str], header: str | None
) -> None:
    # The cookie of a session is no token: the server never reads it.
    headers = {**ACCEPT, "Cookie": signed_in["Cookie"]}
    if header is not None:
        headers["Authorization"] = header

    response = httpx.post(f"{stack.base_url}/mcp", json=INITIALIZE, headers=headers, timeout=30.0)

    assert response.status_code == 401
    assert response.json()["code"] == "not_signed_in"
    assert response.headers["www-authenticate"] == "Bearer"


def test_a_token_revoked_is_refused_at_once(stack: Stack, client: httpx.Client) -> None:
    created = new_access_token(client, "write")
    url = f"{stack.base_url}/mcp"
    headers = {**ACCEPT, **bearer(created["secret"])}
    # The public name of shelfdrop, not a loopback one: the host is not checked.
    public = {**headers, "Host": "shelfdrop.maigo.party"}
    before = httpx.post(url, json=INITIALIZE, headers=public, timeout=30.0)

    client.delete(f"/api/v1/tokens/{created['token']['id']}").raise_for_status()
    after = httpx.post(url, json=INITIALIZE, headers=headers, timeout=30.0)

    assert before.status_code == 200, before.text
    assert before.json()["result"]["serverInfo"]["name"] == "shelfdrop"
    assert before.headers["cache-control"] == "no-store"
    assert after.status_code == 401
    assert after.json()["code"] == "not_signed_in"
