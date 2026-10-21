"""TokenService: the access tokens of the API and of the MCP server (ADR 0020).

A token is a random secret of 256 bits, prefixed `sd_`, shown once at its creation; the database
keeps its SHA-256 alone. A token reads (`read`), or reads and downloads (`write`); it lasts 30
days, 90 days, a year or without end, until it is revoked. Each request it carries is counted:
60 a minute at most. Its creation and its revocation go to the audit, never its secret.
"""

import hashlib
import logging
import secrets
from typing import Final

import anyio
import anyio.to_thread

from shelfdrop.tokens.exceptions import (
    TokenNotFoundError,
    TokenRefusedError,
    TokenThrottledError,
)
from shelfdrop.tokens.repository import TokenRepository
from shelfdrop.tokens.throttle import TokenThrottle
from shelfdrop.tokens.types import AccessToken, NewToken, Scope, StoredToken
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)

PREFIX: Final = "sd_"
SECRET_BYTES: Final = 32
DAY_SECONDS: Final = 24 * 3600
# The last use is written again once this much time passed: not on each request.
USE_SECONDS: Final = 60


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


class TokenService:
    def __init__(self, repository: TokenRepository, throttle: TokenThrottle, clock: Clock) -> None:
        self.repository = repository
        self.throttle = throttle
        self.clock = clock

    async def create(self, name: str, scope: Scope, days: int | None, actor: str) -> NewToken:
        """A new token for `days` days (None: without end); its secret is in the result
        alone."""
        now = int(self.clock.now())
        secret = PREFIX + secrets.token_urlsafe(SECRET_BYTES)
        expires_at = None if days is None else now + days * DAY_SECONDS
        token = await anyio.to_thread.run_sync(
            self.keep, name, fingerprint(secret), scope, actor, now, expires_at
        )
        logger.info("Access token created", extra={"token": token.id, "account": actor})
        return NewToken(token=token, secret=secret)

    def keep(
        self,
        name: str,
        token_hash: str,
        scope: Scope,
        actor: str,
        now: int,
        expires_at: int | None,
    ) -> AccessToken:
        token = self.repository.add(
            name=name,
            token_hash=token_hash,
            scope=scope,
            created_by=actor,
            created_at=now,
            expires_at=expires_at,
        )
        self.repository.add_audit(now, actor, "created", token.id)
        self.repository.commit()
        return token

    async def read_all(self) -> list[AccessToken]:
        return await anyio.to_thread.run_sync(self.repository.list_active)

    async def revoke(self, token_id: int, actor: str) -> None:
        """At once: the next request of the token is refused. Raises TokenNotFoundError."""
        now = int(self.clock.now())
        if not await anyio.to_thread.run_sync(self.end, token_id, actor, now):
            raise TokenNotFoundError
        logger.info("Access token revoked", extra={"token": token_id, "account": actor})

    def end(self, token_id: int, actor: str, now: int) -> bool:
        if self.repository.revoke(token_id, now) is None:
            return False
        self.repository.add_audit(now, actor, "revoked", token_id)
        self.repository.commit()
        return True

    async def check(self, secret: str) -> StoredToken:
        """The token of this secret, counted. Raises TokenRefusedError (unknown, expired,
        revoked) and TokenThrottledError (60 requests a minute)."""
        now = int(self.clock.now())
        if not secret.startswith(PREFIX):
            raise TokenRefusedError
        stored = await anyio.to_thread.run_sync(self.repository.read, fingerprint(secret), now)
        if stored is None:
            logger.info("Access token refused")
            raise TokenRefusedError
        if not self.throttle.allow(stored.id, now):
            logger.warning("Access token throttled", extra={"token": stored.id})
            raise TokenThrottledError
        if stored.last_used_at is None or now - stored.last_used_at >= USE_SECONDS:
            await anyio.to_thread.run_sync(self.touch, stored.id, now)
        return stored

    def touch(self, token_id: int, now: int) -> None:
        self.repository.mark_used(token_id, now)
        self.repository.commit()
