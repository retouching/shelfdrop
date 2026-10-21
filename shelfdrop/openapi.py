"""docs/openapi.json, the OpenAPI document of the API (ADR 0021). `uv run python -m
shelfdrop.openapi`, from the repository root, writes it again; it needs no .env, no database and
no Docker, and starts nothing."""

import json
import secrets
import sys
from pathlib import Path
from typing import Final

from pydantic import SecretStr

from shelfdrop.config import Settings
from shelfdrop.main import build_app

OPENAPI_FILE: Final = Path("docs/openapi.json")


def invented_settings() -> Settings:
    """Settings that name nothing real, on the default prefix: the application is built, never
    started."""
    return Settings(
        _env_file=None,
        contact="docs@example.org",
        secret_key=SecretStr(secrets.token_urlsafe(32)),
        api_prefix="/api",
        static_dir=Path("/nonexistent"),
    )


def document() -> str:
    """The text of the file: indented JSON, keys in the order of the schema, one final newline."""
    schema = build_app(invented_settings()).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    if not OPENAPI_FILE.parent.is_dir():
        sys.stderr.write("error: docs/ not found: run from the repository root\n")
        return 1
    OPENAPI_FILE.write_text(document(), encoding="utf-8", newline="\n")
    sys.stdout.write(f"wrote {OPENAPI_FILE.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
