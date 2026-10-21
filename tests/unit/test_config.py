"""Settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from shelfdrop.config import Settings


def test_the_database_lives_in_the_data_directory(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, contact="test@example.org")

    assert settings.database_url == f"sqlite:///{tmp_path}/shelfdrop.db"


def test_the_contact_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHELFDROP_CONTACT", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("prefix", ["api", "/api/", "/a b", ""])
def test_the_api_prefix_is_a_path(prefix: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, contact="test@example.org", api_prefix=prefix)
