"""The routes of the session: sign in with an account of Jellyfin, read the session, sign out.
Async: the sign-in waits on Jellyfin (plan section 5)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.auth.exceptions import (
    JellyfinUnavailableError,
    LoginRefusedError,
    TooManyAttemptsError,
)
from shelfdrop.auth.service import SESSION_SECONDS, AuthService
from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import SESSION_COOKIE, require_session
from shelfdrop.modules.session.errors import (
    jellyfin_unavailable,
    login_refused,
    too_many_attempts,
)
from shelfdrop.modules.session.schemas import SessionRead, SignInBody

router = APIRouter(prefix="/v1/session", tags=["session"], route_class=WireupRoute)


@router.post("")
async def sign_in(
    request: Request, response: Response, body: SignInBody, auth: Injected[AuthService]
) -> SessionRead:
    """Open a session for an administrator of Jellyfin: the cookie `__Host-shelfdrop`."""
    client = request.client.host if request.client else ""
    try:
        signed_in = await auth.sign_in(body.username, body.password, client)
    except TooManyAttemptsError as exc:
        raise too_many_attempts() from exc
    except LoginRefusedError as exc:
        raise login_refused() from exc
    except JellyfinUnavailableError as exc:
        raise jellyfin_unavailable() from exc
    response.set_cookie(
        SESSION_COOKIE,
        signed_in.token,
        max_age=SESSION_SECONDS,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return SessionRead.model_validate(signed_in.account)


@router.get("")
async def read_session(account: Annotated[Account, Depends(require_session)]) -> SessionRead:
    return SessionRead.model_validate(account)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(
    request: Request,
    response: Response,
    account: Annotated[Account, Depends(require_session)],
    auth: Injected[AuthService],
) -> None:
    await auth.sign_out(request.cookies.get(SESSION_COOKIE, ""))
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
