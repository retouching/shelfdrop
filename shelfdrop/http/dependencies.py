"""What every route shares about the request: the release of its database session, and who
asks: the session of an account signed in, or an access token (ADR 0020)."""

from collections.abc import Iterator
from typing import Final

from fastapi import Request
from sqlalchemy.orm import Session
from wireup import Injected
from wireup.integration.fastapi import inject

from shelfdrop.auth.exceptions import NotSignedInError
from shelfdrop.auth.service import AuthService
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
    administrators (the settings, the trackers, the filters, the tokens); the routes of the
    session ask for it themselves."""
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
