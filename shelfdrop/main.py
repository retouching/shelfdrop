"""Composition root of the HTTP application: create_app() reads the configuration and the files,
build_app() registers the routers, the middlewares and the error handlers and wires the
container (ADR 0004)."""

from importlib.metadata import version

import wireup
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from wireup.integration.fastapi import setup

from shelfdrop.config import Settings
from shelfdrop.container import injectables
from shelfdrop.http.dependencies import release_session
from shelfdrop.http.errors.handlers import (
    handle_http_exception,
    handle_request_validation_error,
    handle_unhandled_exception,
)
from shelfdrop.http.middleware.access_log import AccessLogMiddleware
from shelfdrop.http.middleware.request_id import RequestIdMiddleware
from shelfdrop.http.middleware.security_headers import SecurityHeadersMiddleware
from shelfdrop.http.middleware.unhandled_errors import UnhandledErrorsMiddleware
from shelfdrop.logging.setup import configure_logging
from shelfdrop.modules.health.router import router as health_router
from shelfdrop.modules.web.router import web_router
from shelfdrop.modules.works.router import router as works_router


def create_app() -> FastAPI:
    """Uvicorn factory (`--factory shelfdrop.main:create_app`); fails fast on invalid
    configuration."""
    settings = Settings()
    configure_logging(level=settings.log_level, json_format=settings.log_format == "json")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return build_app(settings)


def build_app(settings: Settings) -> FastAPI:
    """The application for these settings: routers, middlewares, error handlers and the
    container. It configures no logging: create_app() does."""
    prefix = settings.api_prefix
    app = FastAPI(
        title="shelfdrop",
        version=version("shelfdrop"),
        # Neither a schema nor a documentation page: the routes are described in docs/api.md.
        openapi_url=None,
        docs_url=None,
        swagger_ui_oauth2_redirect_url=None,
        redoc_url=None,
        # Every route: the request session is closed in the threadpool after the response.
        dependencies=[Depends(release_session)],
        exception_handlers={
            StarletteHTTPException: handle_http_exception,
            RequestValidationError: handle_request_validation_error,
            # Only reached by exceptions raised outside UnhandledErrorsMiddleware.
            Exception: handle_unhandled_exception,
        },
    )
    # The last middleware added is the outermost one.
    app.add_middleware(UnhandledErrorsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, api_paths=(f"{prefix}/", "/health"))
    app.add_middleware(AccessLogMiddleware, quiet_paths=frozenset({"/health"}))
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    app.include_router(works_router, prefix=prefix)
    # The front-end, last: its route answers every path the others leave.
    if (settings.static_dir / "index.html").is_file():
        for folder in ("assets", "fonts"):
            if (settings.static_dir / folder).is_dir():
                app.mount(f"/{folder}", StaticFiles(directory=settings.static_dir / folder))
        app.include_router(web_router(settings.static_dir, prefix))
    # Last: WireupAsgiMiddleware becomes the outermost middleware and the routes above get their
    # injection; nothing may be added to an included router afterwards.
    container = wireup.create_async_container(injectables=injectables(settings))
    setup(container, app, middleware_mode=True)
    return app
