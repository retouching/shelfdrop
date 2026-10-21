"""What every route shares about the request: the release of its database session, and the
session of the account signed in."""

from collections.abc import Iterator
from typing import Final

from fastapi import Request
from sqlalchemy.orm import Session
from wireup import Injected
from wireup.integration.fastapi import inject

from shelfdrop.auth.exceptions import NotSignedInError
from shelfdrop.auth.service import AuthService
from shelfdrop.auth.types import Account
from shelfdrop.http.errors.errors import not_signed_in

# `__Host-`: the browser keeps the cookie only when it is Secure, on the path /, without a
# Domain: no other host can set it.
SESSION_COOKIE: Final = "__Host-shelfdrop"


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


@inject
async def require_session(request: Request, auth: Injected[AuthService]) -> Account:
    """The account of the session cookie; 401 `not_signed_in` without one. build_app() puts it
    on every router but the one of the session, whose routes ask for it themselves."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise not_signed_in()
    try:
        return await auth.check(token)
    except NotSignedInError as exc:
        raise not_signed_in() from exc
