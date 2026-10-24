"""The routes of the access tokens (the page Paramètres, Accès): list, create (the secret shown
once), revoke. Kept for the session of an administrator: a token never makes another one."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.auth.types import Account
from shelfdrop.http.dependencies import require_session
from shelfdrop.modules.tokens.errors import token_not_found
from shelfdrop.modules.tokens.schemas import TokenCreate, TokenCreated, TokenRead, TokensRead
from shelfdrop.tokens.exceptions import TokenNotFoundError
from shelfdrop.tokens.service import TokenService

router = APIRouter(prefix="/v1/tokens", tags=["tokens"], route_class=WireupRoute)


@router.get("")
async def read_tokens(service: Injected[TokenService]) -> TokensRead:
    """The tokens not revoked, the newest first; never a secret."""
    return TokensRead(tokens=[TokenRead.model_validate(t) for t in await service.read_all()])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_token(
    body: TokenCreate,
    service: Injected[TokenService],
    account: Annotated[Account, Depends(require_session)],
) -> TokenCreated:
    created = await service.create(body.name, body.scope, body.days, account.username)
    return TokenCreated(token=TokenRead.model_validate(created.token), secret=created.secret)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: int,
    service: Injected[TokenService],
    account: Annotated[Account, Depends(require_session)],
) -> None:
    try:
        await service.revoke(token_id, account.username)
    except TokenNotFoundError as exc:
        raise token_not_found() from exc
