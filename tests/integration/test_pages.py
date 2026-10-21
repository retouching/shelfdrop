"""The pages of the front-end, served by the real image."""

import httpx
import pytest

pytestmark = pytest.mark.pages


def test_the_root_is_the_index(client: httpx.Client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root">' in response.text


@pytest.mark.parametrize("path", ["/telechargements", "/ranger/inbox", "/a/b/c"])
def test_any_other_page_is_the_index(client: httpx.Client, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.text == client.get("/").text


def test_the_assets_of_the_index_are_served(client: httpx.Client) -> None:
    index = client.get("/").text
    script = index.split('src="', 1)[1].split('"', 1)[0]

    response = client.get(script)

    assert script.startswith("/assets/")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


def test_the_icon_and_the_font_are_served(client: httpx.Client) -> None:
    icon = client.get("/favicon.svg")
    font = client.get("/fonts/outfit-latin.woff2")

    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/svg+xml")
    assert font.status_code == 200
    assert font.headers["content-type"] == "font/woff2"


@pytest.mark.parametrize("path", ["/api", "/api/", "/api/v1", "/api/v2/works"])
def test_the_api_prefix_never_falls_back_to_a_page(client: httpx.Client, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_a_path_never_leaves_the_build(client: httpx.Client) -> None:
    response = client.get("/..%2F..%2Fetc%2Fpasswd")

    assert response.status_code == 200
    assert "root:" not in response.text
