"""shelfdrop.modules.mcp.router: the tools of the MCP server and what they need."""

import pytest
from fastapi import FastAPI
from mcp import Client

from shelfdrop.modules.mcp.router import new_mcp_server

TOOLS = {
    "search_works": True,
    "search_releases": True,
    "grab_releases": False,
    "list_downloads": True,
    "retry_download": False,
    "list_files_to_place": True,
    "place_file": False,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_tools_of_the_plan_and_which_ones_only_read() -> None:
    server = new_mcp_server(FastAPI(), "1.2.3")

    async with Client(server) as client:
        listed = await client.list_tools()

    found = {tool.name: tool.annotations for tool in listed.tools}
    assert list(found) == list(TOOLS)
    for name, reads in TOOLS.items():
        annotations = found[name]
        assert annotations is not None
        assert annotations.read_only_hint is reads, name
    grab = next(tool for tool in listed.tools if tool.name == "grab_releases")
    assert set(grab.input_schema["required"]) == {"search_id", "releases"}
    assert "ctx" not in grab.input_schema["properties"]


@pytest.mark.anyio
async def test_a_write_without_the_request_of_a_token_is_refused() -> None:
    server = new_mcp_server(FastAPI(), "1.2.3")

    async with Client(server) as client:
        result = await client.call_tool("retry_download", {"download_id": 1})

    assert result.is_error
    assert "not_signed_in" in str(result.content)
