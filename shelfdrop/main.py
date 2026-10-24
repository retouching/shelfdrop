"""Composition root of the HTTP application: create_app() reads the configuration and the files,
build_app() registers the routers, the middlewares and the error handlers and wires the
container (ADR 0004)."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from importlib.metadata import version
from typing import Final

import wireup
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from wireup.integration.fastapi import get_app_container, setup

from shelfdrop.config import Settings
from shelfdrop.container import environment_values, injectables
from shelfdrop.downloads.sender import DownloadSender
from shelfdrop.http.dependencies import (
    check_token,
    release_session,
    require_access,
    require_reader,
    require_session,
)
from shelfdrop.http.errors.handlers import (
    handle_http_exception,
    handle_request_validation_error,
    handle_unhandled_exception,
)
from shelfdrop.http.middleware.access_log import AccessLogMiddleware
from shelfdrop.http.middleware.mcp import McpMiddleware
from shelfdrop.http.middleware.origin import OriginMiddleware
from shelfdrop.http.middleware.request_id import RequestIdMiddleware
from shelfdrop.http.middleware.security_headers import SecurityHeadersMiddleware
from shelfdrop.http.middleware.unhandled_errors import UnhandledErrorsMiddleware
from shelfdrop.http.openapi import DocumentedApi
from shelfdrop.journal.service import JournalSender
from shelfdrop.library.sync import LibrarySync
from shelfdrop.logging.setup import configure_logging, log_file
from shelfdrop.modules.docs.router import docs_router
from shelfdrop.modules.downloads.router import router as downloads_router
from shelfdrop.modules.filters.router import router as filters_router
from shelfdrop.modules.health.router import router as health_router
from shelfdrop.modules.library.router import router as library_router
from shelfdrop.modules.logs.router import router as logs_router
from shelfdrop.modules.mcp.router import new_mcp_server
from shelfdrop.modules.place.router import router as place_router
from shelfdrop.modules.releases.router import router as releases_router
from shelfdrop.modules.searches.router import router as searches_router
from shelfdrop.modules.session.router import router as session_router
from shelfdrop.modules.settings.router import router as settings_router
from shelfdrop.modules.tokens.router import router as tokens_router
from shelfdrop.modules.trackers.router import router as trackers_router
from shelfdrop.modules.uploads.router import router as uploads_router
from shelfdrop.modules.waiting.router import router as waiting_router
from shelfdrop.modules.web.router import web_router
from shelfdrop.modules.works.router import router as works_router
from shelfdrop.settings.monitor import ConnectionMonitor
from shelfdrop.settings.service import SettingsService
from shelfdrop.waiting.service import WaitingRunner

logger = logging.getLogger(__name__)

# The path of the MCP server, outside the prefix of the API.
MCP_PATH: Final = "/mcp"


def create_app() -> FastAPI:
    """Uvicorn factory (`--factory shelfdrop.main:create_app`); fails fast on invalid
    configuration."""
    settings = Settings()
    configure_logging(
        level=settings.log_level,
        json_format=settings.log_format == "json",
        file=log_file(settings.log_dir, "api"),
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return build_app(settings)


def build_app(settings: Settings) -> DocumentedApi:
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
        library_sync = await container.get(LibrarySync)
        loops = [
            asyncio.create_task(monitor.run()),
            asyncio.create_task(journal.run()),
            asyncio.create_task(waiting.run()),
        ]
        try:
            async with mcp_server.session_manager.run():
                yield
        finally:
            for loop in loops:
                loop.cancel()
            for loop in loops:
                with contextlib.suppress(asyncio.CancelledError):
                    await loop
            await sender.close()
            await library_sync.close()

    app = DocumentedApi(
        lifespan=lifespan,
        title="shelfdrop",
        version=version("shelfdrop"),
        # The public document and its page are routes of the API, for a session or a token
        # (ADR 0021).
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
    # The MCP server (ADR 0022): stateless, JSON answers, behind an access token; the host is
    # not checked (the token is what a page of another site cannot send).
    mcp_server = new_mcp_server(app, version("shelfdrop"))
    mcp_app = mcp_server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    # The last middleware added is the outermost one.
    app.add_middleware(
        McpMiddleware, path=MCP_PATH, server=mcp_app, check=partial(check_token, app)
    )
    app.add_middleware(OriginMiddleware, api_paths=(f"{prefix}/",))
    app.add_middleware(UnhandledErrorsMiddleware)
    app.add_middleware(
        SecurityHeadersMiddleware,
        api_paths=(f"{prefix}/", "/health", MCP_PATH),
        docs_path=f"{prefix}/docs",
    )
    # The logs are read again every 5 seconds by their page: their reads would fill their file.
    app.add_middleware(AccessLogMiddleware, quiet_paths=frozenset({"/health", f"{prefix}/v1/logs"}))
    app.add_middleware(RequestIdMiddleware)
    app.include(health_router)
    # The session asks for itself; every other route of the API needs one, or
    # an access token where one may go (ADR 0020).
    app.include(session_router, prefix=prefix)
    for router in (settings_router, trackers_router, filters_router, tokens_router, logs_router):
        app.include(router, prefix=prefix, guard=require_session)
    for router in (searches_router, releases_router, docs_router(settings.static_dir)):
        app.include(router, prefix=prefix, guard=require_reader)
    for router in (
        works_router,
        downloads_router,
        library_router,
        waiting_router,
        place_router,
        uploads_router,
    ):
        app.include(router, prefix=prefix, guard=require_access)
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
