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
    recorded_stubs,
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
        FakeSources(built.sources_url).load(recorded_stubs())
        yield built
    finally:
        compose(project, "down", "--volumes", "--remove-orphans")


@pytest.fixture
def fake_sources(stack: Stack) -> FakeSources:
    return FakeSources(stack.sources_url)


@pytest.fixture
def client(stack: Stack) -> Iterator[httpx.Client]:
    """A client whose requests carry a unique X-Request-ID, to find their log records."""
    with httpx.Client(base_url=stack.base_url, timeout=30.0) as http_client:
        yield http_client
