"""The migrations of the real image: applied at start, at head, and the data kept across a
restart. Last of the part `security`: it restarts the API."""

import httpx
import pytest

from tests.integration.support import Stack, compose

pytestmark = [pytest.mark.security, pytest.mark.security_migrations]


def test_the_database_is_at_head(stack: Stack) -> None:
    result = stack.exec_api("shelfdrop", "db", "check")

    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith("the database matches the models\n")


def test_an_upgrade_at_head_changes_nothing(stack: Stack) -> None:
    result = stack.exec_api("shelfdrop", "db", "upgrade")

    assert result.returncode == 0, result.stderr


def test_a_work_found_survives_a_restart(stack: Stack, client: httpx.Client) -> None:
    found = client.get("/api/v1/works", params={"q": "Berserk", "kind": "manga"})
    work_id = found.json()["works"][0]["id"]

    restart = compose(stack.project, "restart", "api")
    wait = compose(stack.project, "up", "--detach", "--wait", "--wait-timeout", "60", "api")
    # A restart draws a new loopback port: the next tests read it from the stack.
    stack.read_ports()

    assert restart.returncode == 0, restart.stderr
    assert wait.returncode == 0, wait.stderr
    with httpx.Client(base_url=stack.base_url, timeout=30.0) as again:
        read = again.get(f"/api/v1/works/{work_id}")
    assert read.status_code == 200
    assert read.json()["id"] == work_id
