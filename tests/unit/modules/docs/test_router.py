"""shelfdrop.modules.docs.router: the public document and the page of Swagger UI that shows it,
under a policy that loads the scripts and the styles of the same origin alone."""

import re
from pathlib import Path

import pytest

from tests.unit.test_layers import ROOT
from tests.unit.test_main import client_for, settings_for

SOURCE_PAGE = ROOT / "web" / "swagger" / "index.html"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_page_loads_the_same_origin_alone_and_is_never_cached(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        page = await client.get("/api/docs")

    parts = (part.split(" ", 1) for part in page.headers["content-security-policy"].split("; "))
    policy = {name: value for name, value in parts}
    assert page.status_code == 200
    assert policy["default-src"] == "'none'"
    assert policy["script-src"] == "'self'"
    assert policy["style-src"] == "'self'"
    assert policy["connect-src"] == "'self'"
    assert policy["img-src"] == "'self' data:"
    assert policy["frame-ancestors"] == "'none'"
    assert "unsafe" not in page.headers["content-security-policy"]
    assert page.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_the_other_routes_of_the_api_keep_the_policy_of_the_api(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        document = await client.get("/api/v1/openapi.json")

    assert document.headers["content-security-policy"].startswith("default-src 'none'")
    assert "script-src" not in document.headers["content-security-policy"]


@pytest.mark.anyio
async def test_the_page_is_not_found_without_the_build(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path, pages=False)) as client:
        page = await client.get("/api/docs")
        document = await client.get("/api/v1/openapi.json")

    assert page.status_code == 404
    assert page.json()["code"] == "not_found"
    assert document.status_code == 200


def test_the_source_of_the_page_has_no_inline_script_nor_style() -> None:
    page = SOURCE_PAGE.read_text(encoding="utf-8")

    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", page, flags=re.DOTALL)
    assert scripts == [""]
    assert re.search(r'<script type="module" src="/src/docs.ts">', page)
    assert "<style" not in page
    assert "style=" not in page
    assert "http" not in page
