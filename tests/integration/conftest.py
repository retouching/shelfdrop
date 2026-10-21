"""Integration fixtures: one throwaway Compose stack per pytest session."""

import secrets
from collections.abc import Iterator

import httpx
import pytest

from tests.integration.support import (
    UP_TIMEOUT_SECONDS,
    FakeSources,
    Stack,
    compose,
    cookie_of,
    jellyfin_stubs,
    prowlarr_stubs,
    recorded_stubs,
    sign_in,
    signed_in_headers,
)


@pytest.fixture(scope="session")
def stack() -> Iterator[Stack]:
    project = f"shelfdrop-test-{secrets.token_hex(4)}"
    try:
        up = compose(
            project,
            "up",
            "--detach",
            "--build",
            "--wait",
            "--wait-timeout",
            "180",
            timeout=UP_TIMEOUT_SECONDS,
        )
        if up.returncode != 0:
            logs = compose(project, "logs", "--no-color")
            pytest.fail(
                f"`docker compose up` failed for {project}:\n{up.stderr}\n"
                f"--- logs ---\n{logs.stdout}{logs.stderr}",
                pytrace=False,
            )
        built = Stack(project=project)
        try:
            built.read_ports()
        except RuntimeError as error:
            pytest.fail(str(error), pytrace=False)
        FakeSources(built.sources_url).load(
            [*recorded_stubs(), *prowlarr_stubs(), *jellyfin_stubs()]
        )
        yield built
    finally:
        compose(project, "down", "--volumes", "--remove-orphans")


@pytest.fixture
def fake_sources(stack: Stack) -> FakeSources:
    return FakeSources(stack.sources_url)


@pytest.fixture(scope="session")
def session_token(stack: Stack) -> str:
    """One session of the administrator for the whole run: the sign-ins are counted (5 a
    minute from one address), the tests of the sign-in make their own."""
    response = sign_in(stack.base_url)
    assert response.status_code == 200, response.text
    return cookie_of(response)


@pytest.fixture
def signed_in(stack: Stack, session_token: str) -> dict[str, str]:
    """The headers of a request of the pages, signed in, for the port of now."""
    return signed_in_headers(stack.base_url, session_token)


@pytest.fixture
def client(stack: Stack, signed_in: dict[str, str]) -> Iterator[httpx.Client]:
    """A client of the pages, signed in as the administrator."""
    with httpx.Client(base_url=stack.base_url, timeout=30.0, headers=signed_in) as http_client:
        yield http_client


@pytest.fixture
def anonymous(stack: Stack) -> Iterator[httpx.Client]:
    """A client without a session, from the pages (its Origin)."""
    headers = {"Origin": stack.base_url}
    with httpx.Client(base_url=stack.base_url, timeout=30.0, headers=headers) as http_client:
        yield http_client
