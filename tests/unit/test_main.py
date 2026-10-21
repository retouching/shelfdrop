"""The HTTP application: the liveness probe, the error bodies, the headers and the pages."""

from pathlib import Path

import httpx
import pytest

from shelfdrop.config import Settings
from shelfdrop.main import build_app


def settings_for(tmp_path: Path, *, pages: bool = True) -> Settings:
    static = tmp_path / "static"
    if pages:
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<!doctype html><title>shelfdrop</title>")
        (static / "favicon.svg").write_text("<svg/>")
        (static / "assets" / "app.js").write_text("void 0")
    return Settings(data_dir=tmp_path / "data", static_dir=static, contact="test@example.org")


def client_for(settings: Settings) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=build_app(settings))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_answers_without_io(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-security-policy"].startswith("default-src 'none'")
    assert "x-request-id" in response.headers


@pytest.mark.anyio
async def test_an_unknown_api_path_is_a_json_404(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.get("/api/v1/nothing")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "detail": "Not Found", "data": None}


@pytest.mark.anyio
async def test_a_short_query_is_refused_before_any_source(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.get("/api/v1/works", params={"q": "a"})

    assert response.status_code == 422
    assert response.json()["code"] == "query_too_short"


@pytest.mark.anyio
async def test_a_validation_error_never_echoes_the_input(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.get("/api/v1/works", params={"q": "Berserk", "kind": "secret-x"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert "secret-x" not in response.text


@pytest.mark.anyio
async def test_the_pages_fall_back_to_the_index(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        asset = await client.get("/assets/app.js")
        icon = await client.get("/favicon.svg")
        page = await client.get("/telechargements")
        escape = await client.get("/..%2Fpyproject.toml")

    assert asset.status_code == 200
    assert icon.text == "<svg/>"
    assert "<title>shelfdrop</title>" in page.text
    assert page.headers["cache-control"] == "no-cache"
    assert page.headers["content-security-policy"].startswith("default-src 'self'")
    assert "<title>shelfdrop</title>" in escape.text


@pytest.mark.anyio
async def test_without_a_build_no_page_is_served(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path, pages=False)) as client:
        response = await client.get("/")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
