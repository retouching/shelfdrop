"""The routes of the internal account, from the settings (ADR 0023): read it, create it (an
installation signed in through Jellyfin), change its password. Async: a hash waits in the
threadpool."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.accounts.exceptions import (
    AccountExistsError,
    AccountMissingError,
    PasswordRefusedError,
)
from shelfdrop.accounts.service import AccountService
from shelfdrop.auth.service import AuthService
from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import SESSION_COOKIE, require_session
from shelfdrop.modules.account.errors import account_exists, account_not_found, password_refused
from shelfdrop.modules.account.schemas import AccountBody, AccountRead, AccountState, PasswordBody

router = APIRouter(prefix="/v1/account", tags=["account"], route_class=WireupRoute)


@router.get("")
async def read_account(service: Injected[AccountService]) -> AccountState:
    view = await service.read()
    return AccountState(account=None if view is None else AccountRead.model_validate(view))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountBody, service: Injected[AccountService]) -> AccountRead:
    """The internal account of an installation signed in through Jellyfin alone."""
    try:
        view = await service.create(body.username, body.password, setup=False)
    except AccountExistsError as exc:
        raise account_exists() from exc
    return AccountRead.model_validate(view)


@router.put("/password")
async def change_password(
    request: Request,
    body: PasswordBody,
    account: Annotated[Account, Depends(require_session)],
    service: Injected[AccountService],
    auth: Injected[AuthService],
) -> AccountRead:
    """A new password, the current one given; the sessions of the internal account end, but
    the one of the request."""
    try:
        view = await service.change_password(body.current, body.new)
    except AccountMissingError as exc:
        raise account_not_found() from exc
    except PasswordRefusedError as exc:
        raise password_refused() from exc
    kept = request.cookies.get(SESSION_COOKIE) if account.internal else None
    await auth.end_other_internal_sessions(kept)
    return AccountRead.model_validate(view)
