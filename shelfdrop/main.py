"""Composition root of the HTTP application: create_app() reads the configuration and the files,
build_app() registers the routers, the middlewares and the error handlers and wires the
container (ADR 0004)."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

import wireup
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from wireup.integration.fastapi import get_app_container, setup

from shelfdrop.config import Settings
from shelfdrop.container import environment_values, injectables
from shelfdrop.downloads.sender import DownloadSender
from shelfdrop.http.dependencies import release_session, require_session
from shelfdrop.http.errors.handlers import (
    handle_http_exception,
    handle_request_validation_error,
    handle_unhandled_exception,
)
from shelfdrop.http.middleware.access_log import AccessLogMiddleware
from shelfdrop.http.middleware.origin import OriginMiddleware
from shelfdrop.http.middleware.request_id import RequestIdMiddleware
from shelfdrop.http.middleware.security_headers import SecurityHeadersMiddleware
from shelfdrop.http.middleware.unhandled_errors import UnhandledErrorsMiddleware
from shelfdrop.journal.service import JournalSender
from shelfdrop.logging.setup import configure_logging
from shelfdrop.modules.downloads.router import router as downloads_router
from shelfdrop.modules.filters.router import router as filters_router
from shelfdrop.modules.health.router import router as health_router
from shelfdrop.modules.library.router import router as library_router
from shelfdrop.modules.place.router import router as place_router
from shelfdrop.modules.releases.router import router as releases_router
from shelfdrop.modules.searches.router import router as searches_router
from shelfdrop.modules.session.router import router as session_router
from shelfdrop.modules.settings.router import router as settings_router
from shelfdrop.modules.trackers.router import router as trackers_router
from shelfdrop.modules.waiting.router import router as waiting_router
from shelfdrop.modules.web.router import web_router
from shelfdrop.modules.works.router import router as works_router
from shelfdrop.settings.monitor import ConnectionMonitor
from shelfdrop.settings.service import SettingsService
from shelfdrop.waiting.service import WaitingRunner

logger = logging.getLogger(__name__)


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """At start: the settings of the environment imported once into the database
        (ADR 0012), the sends a stop left unfinished (ADR 0014), then the tests of the services
        every 5 minutes, the messages of the journal (ADR 0015) and the rounds of the waiting
        searches (ADR 0017), until the end."""
        container = get_app_container(app)
        async with container.enter_scope() as scope:
            service = await scope.get(SettingsService)
            imported = await service.import_environment(environment_values(settings))
        if imported:
            logger.info("Settings imported from the environment", extra={"keys": imported})
        sender = await container.get(DownloadSender)
        await sender.resume()
        monitor = await container.get(ConnectionMonitor)
        journal = await container.get(JournalSender)
        waiting = await container.get(WaitingRunner)
        loops = [
            asyncio.create_task(monitor.run()),
            asyncio.create_task(journal.run()),
            asyncio.create_task(waiting.run()),
        ]
        try:
            yield
        finally:
            for loop in loops:
                loop.cancel()
            for loop in loops:
                with contextlib.suppress(asyncio.CancelledError):
                    await loop
            await sender.close()

    app = FastAPI(
        lifespan=lifespan,
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
    app.add_middleware(OriginMiddleware, api_paths=(f"{prefix}/",))
    app.add_middleware(UnhandledErrorsMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, api_paths=(f"{prefix}/", "/health"))
    app.add_middleware(AccessLogMiddleware, quiet_paths=frozenset({"/health"}))
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    # The session asks for itself; every other route of the API needs one (plan section 5).
    app.include_router(session_router, prefix=prefix)
    signed_in = [Depends(require_session)]
    for router in (
        works_router,
        searches_router,
        releases_router,
        downloads_router,
        trackers_router,
        filters_router,
        settings_router,
        library_router,
        waiting_router,
        place_router,
    ):
        app.include_router(router, prefix=prefix, dependencies=signed_in)
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
