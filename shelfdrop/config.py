"""Runtime configuration read from SHELFDROP_* environment variables (and an optional .env).

Only what the process needs before its database is open lives here.
"""

from pathlib import Path
from typing import Any, Final, Literal, override

from pydantic import Field, SecretStr, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

DEFAULT_STATIC_DIR: Final = Path(__file__).resolve().parent / "static"
# The settings reserved for the test stack: `docker/compose.test.yaml` alone sets them, through
# the environment of the process, and a `.env` file never does (ADR 0010).
TEST_STACK_SETTINGS: Final = frozenset(
    {"sources_origin", "source_rest_seconds", "send_check_seconds", "journal_batch_seconds"}
)
# The address of a service: http(s), a host, a port, a path.
ADDRESS_PATTERN: Final = r"^https?://[A-Za-z0-9.-]+(:\d+)?(/.*)?$"


class EnvFileWithoutTestSettings(PydanticBaseSettingsSource):
    """What the `.env` file gives, but the settings reserved for the test stack."""

    def __init__(
        self, settings_cls: type[BaseSettings], source: PydanticBaseSettingsSource
    ) -> None:
        super().__init__(settings_cls)
        self.source = source

    @override
    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self.source.get_field_value(field, field_name)

    @override
    def __call__(self) -> dict[str, Any]:
        return {
            name: value for name, value in self.source().items() if name not in TEST_STACK_SETTINGS
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHELFDROP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            EnvFileWithoutTestSettings(settings_cls, dotenv_settings),
            file_secret_settings,
        )

    # The directory of the database (shelfdrop.db).
    data_dir: Path = Path(".data")
    # The built front-end (web/dist); the API serves no page when it holds no index.html.
    static_dir: Path = DEFAULT_STATIC_DIR
    # Every route but /health and the pages is served under this prefix.
    api_prefix: str = Field(default="/api", pattern=r"^(?:/[A-Za-z0-9_-]+)+$")
    # Written in the User-Agent of every request to a metadata source, as their usage policies
    # ask: an address where the operator can be reached.
    contact: str = Field(min_length=3)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    # The key the secrets of the database are sealed with (ADR 0012): 32 random bytes or more,
    # written as text (`openssl rand -base64 32`). The API does not start without it.
    secret_key: SecretStr | None = Field(default=None, min_length=32, repr=False)
    # The address of the pages, as the browser reaches them (https://shelfdrop.maigo.party):
    # the title of each message of the journal links there. None: no link.
    public_url: str | None = Field(default=None, pattern=ADDRESS_PATTERN)
    # The five settings below are imported once into the database, at the first start where
    # they are set; then the settings page holds them (ADR 0012).
    # The Client ID of the MyAnimeList API.
    myanimelist_client_id: SecretStr | None = Field(default=None, repr=False)
    # The address of Prowlarr (http://host:9696) and its API key.
    prowlarr_url: str | None = Field(default=None, pattern=ADDRESS_PATTERN)
    prowlarr_api_key: SecretStr | None = Field(default=None, repr=False)
    # The address of Jellyfin (http://host:8096): the accounts sign in there.
    jellyfin_url: str | None = Field(default=None, pattern=ADDRESS_PATTERN)
    # The webhook of Discord the journal posts on.
    discord_webhook: SecretStr | None = Field(default=None, repr=False)
    # The four settings below are reserved for the test stack (TEST_STACK_SETTINGS).
    # Every request to a metadata source goes to this origin instead, its own origin in the
    # header X-Original-Origin: the fake sources of the test stack answer it.
    sources_origin: str | None = Field(default=None, pattern=r"^https?://[A-Za-z0-9.-]+(:\d+)?$")
    # Seconds a source that failed is skipped.
    source_rest_seconds: int = Field(default=300, ge=0, le=86400)
    # Seconds between two looks for a torrent sent to qBittorrent (ADR 0014).
    send_check_seconds: float = Field(default=8.0, ge=0, le=60)
    # Seconds the events of one batch of the journal wait for the others (ADR 0015).
    journal_batch_seconds: int = Field(default=30, ge=0, le=600)

    @field_validator(
        "secret_key",
        "myanimelist_client_id",
        "prowlarr_url",
        "prowlarr_api_key",
        "jellyfin_url",
        "discord_webhook",
        "public_url",
        mode="before",
    )
    @classmethod
    def empty_is_none(cls, value: object) -> object:
        """Compose gives an unset variable as an empty string."""
        return None if value == "" else value

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'shelfdrop.db'}"
