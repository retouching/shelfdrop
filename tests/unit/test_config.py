"""Settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from shelfdrop.config import TEST_STACK_SETTINGS, Settings


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


def test_a_env_file_never_sets_a_test_stack_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SHELFDROP_CONTACT=test@example.org\n"
        "SHELFDROP_SOURCES_ORIGIN=http://elsewhere:8080\n"
        "SHELFDROP_SOURCE_REST_SECONDS=0\n"
    )
    monkeypatch.delenv("SHELFDROP_SOURCES_ORIGIN", raising=False)
    monkeypatch.delenv("SHELFDROP_SOURCE_REST_SECONDS", raising=False)

    settings = Settings(_env_file=env_file)

    assert settings.contact == "test@example.org"
    assert settings.sources_origin is None
    assert settings.source_rest_seconds == 300


def test_the_environment_sets_the_test_stack_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHELFDROP_SOURCES_ORIGIN", "http://fake-sources:8080")
    monkeypatch.setenv("SHELFDROP_SOURCE_REST_SECONDS", "0")

    settings = Settings(_env_file=None, contact="test@example.org")

    assert settings.sources_origin == "http://fake-sources:8080"
    assert settings.source_rest_seconds == 0


@pytest.mark.parametrize("name", sorted(TEST_STACK_SETTINGS))
def test_a_test_stack_setting_is_only_in_the_test_stack(name: str) -> None:
    variable = f"SHELFDROP_{name.upper()}"
    root = Path(__file__).resolve().parents[2]

    assert variable not in (root / ".env.example").read_text()
    assert variable not in (root / "docker" / "compose.yaml").read_text()
    assert variable in (root / "docker" / "compose.test.yaml").read_text()


def test_the_myanimelist_client_id_is_never_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHELFDROP_MYANIMELIST_CLIENT_ID", "secret-client-id-5b")

    settings = Settings(_env_file=None, contact="test@example.org")

    assert settings.myanimelist_client_id is not None
    assert settings.myanimelist_client_id.get_secret_value() == "secret-client-id-5b"
    assert "secret-client-id-5b" not in repr(settings)
