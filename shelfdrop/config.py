"""Runtime configuration read from SHELFDROP_* environment variables (and an optional .env).

Only what the process needs before its database is open lives here.
"""

from pathlib import Path
from typing import Final, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_STATIC_DIR: Final = Path(__file__).resolve().parent / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHELFDROP_", env_file=".env", extra="ignore", frozen=True
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

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'shelfdrop.db'}"
