"""The routes of the set-up of the first launch (ADR 0024): its state, the internal account
(the first step, open to anyone while no account exists), the end. Async: a hash waits in the
threadpool, the end waits on the test of Jellyfin."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.accounts.exceptions import (
    AccountExistsError,
    AccountMissingError,
    JellyfinNotConnectedError,
    SetupDoneError,
)
from shelfdrop.accounts.service import AccountService
from shelfdrop.auth.exceptions import LoginRefusedError, TooManyAttemptsError
from shelfdrop.auth.service import AuthService
from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import require_session, set_session_cookie
from shelfdrop.modules.account.schemas import AccountBody
from shelfdrop.modules.session.errors import login_refused, too_many_attempts
from shelfdrop.modules.session.schemas import SessionRead
from shelfdrop.modules.setup.errors import (
    account_exists,
    account_not_found,
    jellyfin_not_connected,
    setup_done,
)
from shelfdrop.modules.setup.schemas import SetupRead

router = APIRouter(prefix="/v1/setup", tags=["setup"], route_class=WireupRoute)


@router.get("")
async def read_setup(service: Injected[AccountService]) -> SetupRead:
    return SetupRead.model_validate(await service.setup_state())


@router.post("/account")
async def create_account(
    request: Request,
    response: Response,
    body: AccountBody,
    service: Injected[AccountService],
    auth: Injected[AuthService],
) -> SessionRead:
    """The first step: the internal account, while the set-up is needed and no account
    exists (the first request wins); its session is opened."""
    try:
        await service.create(body.username, body.password, setup=True)
    except SetupDoneError as exc:
        raise setup_done() from exc
    except AccountExistsError as exc:
        raise account_exists() from exc
    client = request.client.host if request.client else ""
    try:
        signed_in = await auth.sign_in(body.username, body.password, client)
    except TooManyAttemptsError as exc:
        raise too_many_attempts() from exc
    except LoginRefusedError as exc:
        raise login_refused() from exc
    set_session_cookie(response, signed_in.token)
    return SessionRead.model_validate(signed_in.account)


@router.post("/finish")
async def finish_setup(
    account: Annotated[Account, Depends(require_session)], service: Injected[AccountService]
) -> SetupRead:
    """The last step: the set-up ends once the Jellyfin saved answers its test, and the rest
    of the API opens."""
    try:
        await service.finish_setup()
    except SetupDoneError as exc:
        raise setup_done() from exc
    except AccountMissingError as exc:
        raise account_not_found() from exc
    except JellyfinNotConnectedError as exc:
        raise jellyfin_not_connected() from exc
    return SetupRead.model_validate(await service.setup_state())
