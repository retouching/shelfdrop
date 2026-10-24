"""docs/openapi.json, the OpenAPI document of every route of the API, and docs/openapi.public.json,
the one served to the access tokens (ADR 0021). `uv run python -m shelfdrop.openapi`, from the
repository root, writes them again; it needs no .env, no database and no Docker, and starts
nothing."""

import json
import secrets
import sys
from pathlib import Path
from typing import Final

from pydantic import SecretStr

from shelfdrop.config import Settings
from shelfdrop.main import build_app

OPENAPI_FILE: Final = Path("docs/openapi.json")
PUBLIC_OPENAPI_FILE: Final = Path("docs/openapi.public.json")


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


def documents() -> dict[Path, str]:
    """The text of each file: indented JSON, keys in the order of the schema, one final
    newline."""
    app = build_app(invented_settings())
    return {
        OPENAPI_FILE: json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n",
        PUBLIC_OPENAPI_FILE: json.dumps(app.public_openapi(), indent=2, ensure_ascii=False) + "\n",
    }


def main() -> int:
    if not OPENAPI_FILE.parent.is_dir():
        sys.stderr.write("error: docs/ not found: run from the repository root\n")
        return 1
    for path, text in documents().items():
        path.write_text(text, encoding="utf-8", newline="\n")
        sys.stdout.write(f"wrote {path.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
