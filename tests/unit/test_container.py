"""shelfdrop.container: the values of the environment imported into the settings, the key of the
secrets."""

import pytest
from pydantic import SecretStr

from shelfdrop.config import Settings
from shelfdrop.container import environment_values, new_secret_box


def test_the_environment_gives_the_settings_it_sets_alone() -> None:
    settings = Settings(
        _env_file=None,
        contact="test@example.org",
        prowlarr_url="http://prowlarr:9696",
        prowlarr_api_key=SecretStr("prowlarr-key"),
        jellyfin_url="",
        myanimelist_client_id=None,
        discord_webhook=SecretStr("https://discord.test/api/webhooks/1/t"),
    )

    assert environment_values(settings) == {
        "prowlarr.url": "http://prowlarr:9696",
        "prowlarr.api_key": "prowlarr-key",
        "discord.webhook": "https://discord.test/api/webhooks/1/t",
    }


def test_the_secrets_need_their_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHELFDROP_SECRET_KEY", raising=False)
    settings = Settings(_env_file=None, contact="test@example.org")

    with pytest.raises(RuntimeError, match="SHELFDROP_SECRET_KEY"):
        new_secret_box(settings)


def test_a_short_secret_key_is_refused() -> None:
    with pytest.raises(ValueError, match="secret_key"):
        Settings(_env_file=None, contact="test@example.org", secret_key=SecretStr("short"))
