"""What every route shares about the request: the release of its database session, and who
asks: the session of an account signed in, or an access token (ADR 0020)."""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Final

import anyio
import anyio.to_thread
from fastapi import FastAPI, Request, Response
from sqlalchemy.orm import Session
from wireup import Injected, ScopedAsyncContainer
from wireup.integration.fastapi import get_app_container, inject

from shelfdrop.accounts.gate import SetupGate
from shelfdrop.accounts.service import AccountService
from shelfdrop.auth.exceptions import NotSignedInError
from shelfdrop.auth.service import SESSION_SECONDS, AuthService
from shelfdrop.auth.types import Account
from shelfdrop.http.errors.errors import not_signed_in, token_forbidden, token_throttled
from shelfdrop.tokens.exceptions import TokenRefusedError, TokenThrottledError
from shelfdrop.tokens.service import TokenService
from shelfdrop.tokens.types import Scope, StoredToken

# `__Host-`: the browser keeps the cookie only when it is Secure, on the path /, without a
# Domain: no other host can set it.
SESSION_COOKIE: Final = "__Host-shelfdrop"
# The methods a token of reading may use on the routes open to the tokens.
READS: Final = frozenset({"GET", "HEAD"})


def set_session_cookie(response: Response, token: str) -> None:
    """The cookie of a session opened (the sign-in, the first step of the set-up)."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_SECONDS,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def bearer_of(request: Request) -> str | None:
    """The secret of `Authorization: Bearer <secret>`; "" for another scheme or an empty one,
    None without the header."""
    header = request.headers.get("authorization")
    if header is None:
        return None
    scheme, _, secret = header.partition(" ")
    return secret.strip() if scheme.lower() == "bearer" else ""


def token_account(token: StoredToken) -> Account:
    """The author of what a token does: its name (the journal, the downloads)."""
    return Account(user_id=f"token:{token.id}", username=token.name)


@inject
def release_session(session: Injected[Session]) -> Iterator[None]:
    """Close the request session in the threadpool once the response is sent.

    build_app() registers it on the whole application. Without it the wireup scope would close
    the session on the event loop thread, where a ROLLBACK blocks every other request.
    """
    try:
        yield
    finally:
        session.close()


async def check_cookie(request: Request, auth: AuthService) -> Account:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise not_signed_in()
    try:
        return await auth.check(token)
    except NotSignedInError as exc:
        raise not_signed_in() from exc


async def check_bearer(secret: str, tokens: TokenService, scope: Scope) -> Account:
    """The account of a token that holds `scope`; 401 `not_signed_in` for a token refused,
    whatever is wrong with it."""
    try:
        token = await tokens.check(secret)
    except TokenRefusedError as exc:
        raise not_signed_in() from exc
    except TokenThrottledError as exc:
        raise token_throttled() from exc
    if scope == "write" and token.scope != "write":
        raise token_forbidden()
    return token_account(token)


@inject
async def require_session(request: Request, auth: Injected[AuthService]) -> Account:
    """The account of the session cookie; 401 `not_signed_in` without one, 403
    `token_forbidden` with an access token. build_app() puts it on the routers kept for the
    administrators (the settings, the trackers, the filters, the tokens, the logs); the routes of
    the session ask for it themselves."""
    if bearer_of(request) is not None:
        raise token_forbidden()
    return await check_cookie(request, auth)


@inject
async def require_reader(
    request: Request, auth: Injected[AuthService], tokens: Injected[TokenService]
) -> Account:
    """The session, or any access token: the routers whose every route reads (the searches of
    releases, a torrent). With an `Authorization` header the cookie is never read."""
    secret = bearer_of(request)
    if secret is None:
        return await check_cookie(request, auth)
    return await check_bearer(secret, tokens, "read")


@inject
async def require_access(
    request: Request, auth: Injected[AuthService], tokens: Injected[TokenService]
) -> Account:
    """The session, or an access token: any token for a read (GET), a token `write` for a
    write. With an `Authorization` header the cookie is never read."""
    secret = bearer_of(request)
    if secret is None:
        return await check_cookie(request, auth)
    return await check_bearer(secret, tokens, "read" if request.method in READS else "write")


@asynccontextmanager
async def scope_of(app: FastAPI) -> AsyncIterator[ScopedAsyncContainer]:
    """A scope of the container outside a route (the MCP server, its tools): its database
    session closed in the threadpool at the end, as `release_session` does for a route."""
    async with get_app_container(app).enter_scope() as scope:
        try:
            yield scope
        finally:
            session = await scope.get(Session)
            await anyio.to_thread.run_sync(session.close)


async def check_token(app: FastAPI, secret: str) -> StoredToken:
    """The token of `secret`, outside a route (the MCP server). Raises TokenRefusedError and
    TokenThrottledError."""
    async with scope_of(app) as scope:
        tokens = await scope.get(TokenService)
        return await tokens.check(secret)


async def setup_needed(app: FastAPI) -> bool:
    """Whether the set-up of the first launch is still needed (ADR 0024), outside a route
    (`SetupMiddleware`): once it is known finished, the database is no longer read."""
    gate = await get_app_container(app).get(SetupGate)
    if gate.done:
        return False
    async with scope_of(app) as scope:
        accounts = await scope.get(AccountService)
        return await accounts.setup_needed()
