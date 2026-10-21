"""The pages of the front-end: a known file of the build, or index.html for any other path
outside the API (the front-end routes on its own)."""

import mimetypes
from pathlib import Path

from fastapi import APIRouter
from starlette.responses import FileResponse

from shelfdrop.http.errors.errors import not_found
from shelfdrop.http.errors.types import ErrorCode


def web_router(static_dir: Path, api_prefix: str) -> APIRouter:
    """The router of the built front-end in `static_dir`; build_app() includes it last, and
    mounts `assets/` and `fonts/` itself."""
    # The slim image has no /etc/mime.types: without this, a font would be served as
    # application/octet-stream.
    mimetypes.add_type("font/woff2", ".woff2")
    root = static_dir.resolve()
    index = root / "index.html"
    # The files at the top of the build (favicon.svg...), read once: a path is never joined to
    # the directory.
    files = {path.name: path for path in root.iterdir() if path.is_file()}
    router = APIRouter(include_in_schema=False)

    @router.get("/{path:path}")
    async def page(path: str) -> FileResponse:
        if path == api_prefix.strip("/") or path.startswith(api_prefix.lstrip("/") + "/"):
            raise not_found(ErrorCode.NOT_FOUND, "Not Found")
        if path in files:
            return FileResponse(files[path])
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return router
