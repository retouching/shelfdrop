"""The liveness probe of the real API."""

import httpx
import pytest

from tests.integration.support import Stack, new_request_id

pytestmark = [pytest.mark.security, pytest.mark.security_health]


def test_health_answers_ok(client: httpx.Client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_not_served_under_the_api_prefix(client: httpx.Client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 404


def test_a_success_of_health_is_not_logged_at_info(stack: Stack, client: httpx.Client) -> None:
    request_id = new_request_id()
    probe = client.get("/health", headers={"X-Request-ID": request_id})
    # A request after it, whose record proves the logs were written that far.
    marker = new_request_id()
    client.get("/api/v1/nothing", headers={"X-Request-ID": marker})

    assert probe.status_code == 200
    assert stack.log_records(marker, expected=1)
    assert stack.log_records(request_id, expected=0) == []
