"""shelfdrop.container: the sources a deployment asks."""

import httpx
import pytest

from shelfdrop.config import Settings
from shelfdrop.container import new_work_sources


@pytest.mark.parametrize(("client_id", "asked"), [(None, False), ("", False), ("abc", True)])
def test_myanimelist_is_asked_with_a_client_id_alone(
    monkeypatch: pytest.MonkeyPatch, client_id: str | None, asked: bool
) -> None:
    if client_id is None:
        monkeypatch.delenv("SHELFDROP_MYANIMELIST_CLIENT_ID", raising=False)
    else:
        monkeypatch.setenv("SHELFDROP_MYANIMELIST_CLIENT_ID", client_id)
    settings = Settings(_env_file=None, contact="test@example.org")

    sources = new_work_sources(httpx.AsyncClient(), settings)

    assert ("myanimelist" in [client.name for client in sources.clients]) is asked
