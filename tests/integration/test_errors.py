"""The error bodies of the real API: every error is {"code", "detail", "data"} and a 422 never
repeats what was sent."""

import httpx
import pytest

pytestmark = [pytest.mark.security, pytest.mark.security_errors]

SECRET_LOOKING: str = "x-secret-value-7f3a"


def test_an_unknown_api_path_is_a_json_404(client: httpx.Client) -> None:
    response = client.get("/api/v1/nothing")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "detail": "Not Found", "data": None}


def test_a_wrong_method_is_a_405_with_its_allow_header(client: httpx.Client) -> None:
    response = client.post("/api/v1/works", params={"q": "Berserk"})

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"
    assert response.headers["allow"] == "GET"


def test_a_missing_query_fails_the_validation(client: httpx.Client) -> None:
    response = client.get("/api/v1/works")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    assert body["data"]["errors"][0]["loc"] == ["query", "q"]


def test_a_validation_error_never_repeats_the_value(client: httpx.Client) -> None:
    response = client.get("/api/v1/works", params={"q": "Berserk", "kind": SECRET_LOOKING})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert SECRET_LOOKING not in response.text


def test_a_query_without_two_letters_is_refused(client: httpx.Client) -> None:
    response = client.get("/api/v1/works", params={"q": " ! "})

    assert response.status_code == 422
    assert response.json() == {
        "code": "query_too_short",
        "detail": "The search needs 2 letters or digits",
        "data": None,
    }


def test_an_unknown_work_is_a_404(client: httpx.Client) -> None:
    response = client.get("/api/v1/works/kitsu:0")

    assert response.status_code == 404
    assert response.json()["code"] == "work_not_found"
