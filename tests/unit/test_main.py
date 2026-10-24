"""The HTTP application: the liveness probe, the error bodies, the headers and the pages."""

from pathlib import Path
from typing import Final

import httpx
import pytest
from pydantic import SecretStr

from shelfdrop.auth.types import Account
from shelfdrop.config import Settings
from shelfdrop.http.dependencies import require_access, require_reader, require_session
from shelfdrop.main import build_app


def settings_for(tmp_path: Path, *, pages: bool = True) -> Settings:
    static = tmp_path / "static"
    if pages:
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<!doctype html><title>shelfdrop</title>")
        (static / "favicon.svg").write_text("<svg/>")
        (static / "assets" / "app.js").write_text("void 0")
        (static / "fonts").mkdir()
        (static / "fonts" / "outfit.woff2").write_bytes(b"wOF2")
        (static / "swagger").mkdir()
        (static / "swagger" / "index.html").write_text(
            '<!doctype html><title>shelfdrop API</title><script type="module" src="/assets/s.js">'
            "</script>"
        )
    return Settings(
        data_dir=tmp_path / "data",
        static_dir=static,
        contact="test@example.org",
        secret_key=SecretStr("k" * 32),
    )


ACCOUNT: Final = Account(user_id="u1", username="sylvain")


def client_for(settings: Settings, *, signed_in: bool = True) -> httpx.AsyncClient:
    """A client of the application; `signed_in`: the session is taken as granted, the sign-in
    has its own tests (tests/unit/auth, tests/integration/test_sign_in.py)."""
    app = build_app(settings)
    if signed_in:
        for dependency in (require_session, require_reader, require_access):
            app.dependency_overrides[dependency] = lambda: ACCOUNT
    transport = httpx.ASGITransport(app=app)
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
        font = await client.get("/fonts/outfit.woff2")

    assert asset.status_code == 200
    assert icon.text == "<svg/>"
    assert "<title>shelfdrop</title>" in page.text
    assert page.headers["cache-control"] == "no-cache"
    assert page.headers["content-security-policy"].startswith("default-src 'self'")
    assert "<title>shelfdrop</title>" in escape.text
    assert font.headers["content-type"] == "font/woff2"


@pytest.mark.anyio
async def test_without_a_build_no_page_is_served(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path, pages=False)) as client:
        response = await client.get("/")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/works?q=Berserk"),
        ("GET", "/api/v1/searches/x"),
        ("GET", "/api/v1/searches/x/events"),
        ("GET", "/api/v1/trackers"),
        ("GET", "/api/v1/releases/0123456789abcdef/torrent"),
        ("GET", "/api/v1/downloads"),
        ("POST", "/api/v1/downloads"),
        ("POST", "/api/v1/downloads/1/retry"),
        ("GET", "/api/v1/downloads/1/cover"),
        ("PUT", "/api/v1/filters"),
        ("GET", "/api/v1/session"),
        ("DELETE", "/api/v1/session"),
        ("GET", "/api/v1/logs"),
    ],
)
async def test_without_a_session_the_api_answers_401(
    tmp_path: Path, method: str, path: str
) -> None:
    async with client_for(settings_for(tmp_path), signed_in=False) as client:
        response = await client.request(method, path, headers={"Origin": "http://test"})

    assert response.status_code == 401
    assert response.json() == {"code": "not_signed_in", "detail": "Not signed in", "data": None}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/settings"),
        ("PUT", "/api/v1/settings"),
        ("GET", "/api/v1/trackers"),
        ("PUT", "/api/v1/filters"),
        ("GET", "/api/v1/tokens"),
        ("POST", "/api/v1/tokens"),
        ("DELETE", "/api/v1/tokens/1"),
        ("GET", "/api/v1/session"),
        ("GET", "/api/v1/logs"),
    ],
)
async def test_a_token_never_reaches_the_routes_of_the_administrators(
    tmp_path: Path, method: str, path: str
) -> None:
    async with client_for(settings_for(tmp_path), signed_in=False) as client:
        response = await client.request(
            method, path, headers={"Authorization": "Bearer sd_x", "Origin": "http://test"}
        )

    assert response.status_code == 403
    assert response.json()["code"] == "token_forbidden"


@pytest.mark.anyio
async def test_a_write_with_a_token_needs_no_origin_and_never_reads_the_cookie(
    tmp_path: Path,
) -> None:
    async with client_for(settings_for(tmp_path), signed_in=False) as client:
        client.cookies.set("__Host-shelfdrop", "some-session")
        response = await client.post(
            "/api/v1/downloads/1/retry", headers={"Authorization": "Bearer not-a-token"}
        )

    assert response.status_code == 401
    assert response.json()["code"] == "not_signed_in"


@pytest.mark.anyio
async def test_the_document_of_the_api_and_its_page_need_a_session_or_a_token(
    tmp_path: Path,
) -> None:
    settings = settings_for(tmp_path)
    async with client_for(settings) as client:
        document = await client.get("/api/v1/openapi.json")
        page = await client.get("/api/docs")
    async with client_for(settings, signed_in=False) as anonymous:
        refused = await anonymous.get("/api/docs")
        refused_document = await anonymous.get("/api/v1/openapi.json")

    assert document.status_code == 200
    assert list(document.json()["components"]["securitySchemes"]) == ["token"]
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "shelfdrop API" in page.text
    assert (refused.status_code, refused_document.status_code) == (401, 401)


@pytest.mark.anyio
async def test_the_probe_and_the_pages_need_no_session(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path), signed_in=False) as client:
        health = await client.get("/health")
        page = await client.get("/reglages")

    assert health.status_code == 200
    assert page.status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize(
    "origin", [None, "null", "http://evil.example", "https://test.evil", "ftp://test"]
)
async def test_a_write_from_another_origin_is_refused(tmp_path: Path, origin: str | None) -> None:
    headers = {} if origin is None else {"Origin": origin}
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.post(
            "/api/v1/session", json={"username": "a", "password": "b"}, headers=headers
        )

    assert response.status_code == 403
    assert response.json()["code"] == "origin_refused"
    assert response.headers["cache-control"] == "no-store"
    assert "x-request-id" in response.headers


@pytest.mark.anyio
async def test_a_read_needs_no_origin_and_a_sign_in_never_echoes_its_input(
    tmp_path: Path,
) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        read = await client.get("/api/v1/session")
        refused = await client.post(
            "/api/v1/session",
            json={"username": "secret-name", "password": ""},
            headers={"Origin": "http://test"},
        )

    assert read.json() == {"username": "sylvain"}
    assert refused.status_code == 422
    assert "secret-name" not in refused.text


@pytest.mark.anyio
async def test_the_torrent_of_a_release_no_search_holds_is_a_404(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.get("/api/v1/releases/0123456789abcdef/torrent")

    assert response.status_code == 404
    assert response.json()["code"] == "release_not_found"


@pytest.mark.anyio
async def test_a_download_of_a_search_no_longer_kept_is_a_404(tmp_path: Path) -> None:
    body = {
        "search_id": "gone",
        "releases": [{"id": "0123456789abcdef", "volumes": {"kind": "single", "first": 1}}],
    }
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.post(
            "/api/v1/downloads", json=body, headers={"Origin": "http://test"}
        )

    assert response.status_code == 404
    assert response.json()["code"] == "search_not_found"
