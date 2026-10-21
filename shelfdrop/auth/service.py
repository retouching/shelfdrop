"""AuthService: the sign-in of an administrator of Jellyfin, and the sessions it opens.

A session is a random token of 256 bits in a cookie; the database keeps its SHA-256 alone,
for 30 days. Every 5 minutes at most, Jellyfin confirms the account is still an
administrator, with the access token it gave at sign-in. The credentials typed are sent to
Jellyfin alone: never kept, never logged.
"""

import hashlib
import logging
import secrets
from typing import Final, Protocol

import anyio
import anyio.to_thread

from shelfdrop.auth.exceptions import (
    JellyfinUnavailableError,
    LoginRefusedError,
    NotSignedInError,
    TooManyAttemptsError,
)
from shelfdrop.auth.repository import SessionRepository
from shelfdrop.auth.throttle import LoginThrottle
from shelfdrop.auth.types import Account, SignedIn, StoredSession
from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.types import JellyfinUser
from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.exceptions import SecretUnreadableError
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)

SESSION_SECONDS: Final = 30 * 24 * 3600
CHECK_SECONDS: Final = 300
TOKEN_BYTES: Final = 32


class JellyfinAddress(Protocol):
    """The address of Jellyfin, read at each sign-in and check (the settings page)."""

    async def jellyfin_url(self) -> str | None: ...


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sealed_name(token_hash: str) -> str:
    """The name the access token of Jellyfin is sealed under: bound to its session."""
    return f"session.{token_hash}"


def is_admin(user: JellyfinUser) -> bool:
    return user.administrator and not user.disabled


class AuthService:
    def __init__(
        self,
        repository: SessionRepository,
        jellyfin: JellyfinClient,
        address: JellyfinAddress,
        box: SecretBox,
        throttle: LoginThrottle,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.jellyfin = jellyfin
        self.address = address
        self.box = box
        self.throttle = throttle
        self.clock = clock

    async def sign_in(self, username: str, password: str, client: str) -> SignedIn:
        """Raises TooManyAttemptsError, LoginRefusedError (whatever is wrong with the
        account) and JellyfinUnavailableError."""
        now = int(self.clock.now())
        if not self.throttle.allow(client, now):
            logger.warning("Sign-in throttled")
            raise TooManyAttemptsError
        url = await self.address.jellyfin_url()
        device_id = secrets.token_hex(16)
        try:
            login = await self.jellyfin.authenticate(url, username, password, device_id)
        except ServiceError as exc:
            if exc.refused:
                logger.info("Sign-in refused")
                raise LoginRefusedError from exc
            logger.warning("Jellyfin unavailable", extra={"error": str(exc)})
            raise JellyfinUnavailableError from exc
        if not is_admin(login.user):
            logger.info("Sign-in refused")
            await self.forget_jellyfin(url, login.token, device_id)
            raise LoginRefusedError
        token = secrets.token_urlsafe(TOKEN_BYTES)
        token_hash = fingerprint(token)
        account = Account(user_id=login.user.id, username=login.user.name)
        stored = StoredSession(
            token_hash=token_hash,
            account=account,
            jellyfin_token=self.box.seal(sealed_name(token_hash), login.token),
            device_id=device_id,
            created_at=now,
            expires_at=now + SESSION_SECONDS,
            checked_at=now,
        )
        await anyio.to_thread.run_sync(self.keep, stored, now)
        logger.info("Signed in", extra={"account": account.username})
        return SignedIn(account=account, token=token, expires_at=stored.expires_at)

    def keep(self, stored: StoredSession, now: int) -> None:
        self.repository.remove_expired(now)
        self.repository.add(stored)
        self.repository.commit()

    async def check(self, token: str) -> Account:
        """The account of a session; Jellyfin is asked again when it last confirmed it 5
        minutes ago or more. Raises NotSignedInError."""
        now = int(self.clock.now())
        token_hash = fingerprint(token)
        stored = await anyio.to_thread.run_sync(self.repository.read, token_hash, now)
        if stored is None:
            raise NotSignedInError
        if now - stored.checked_at < CHECK_SECONDS:
            return stored.account
        url = await self.address.jellyfin_url()
        try:
            jellyfin_token = self.box.open(sealed_name(token_hash), stored.jellyfin_token)
            user = await self.jellyfin.current_user(url, jellyfin_token, stored.device_id)
        except SecretUnreadableError as exc:
            await anyio.to_thread.run_sync(self.end, token_hash)
            raise NotSignedInError from exc
        except ServiceError as exc:
            if exc.refused:
                logger.info("Session ended by Jellyfin")
                await anyio.to_thread.run_sync(self.end, token_hash)
            else:
                # Jellyfin does not answer: no confirmation, the session is kept for later.
                logger.warning("Jellyfin unavailable", extra={"error": str(exc)})
            raise NotSignedInError from exc
        if not is_admin(user) or user.id != stored.account.user_id:
            logger.info("Session ended: no longer an administrator")
            await anyio.to_thread.run_sync(self.end, token_hash)
            raise NotSignedInError
        await anyio.to_thread.run_sync(self.confirm, token_hash, now)
        return stored.account

    def confirm(self, token_hash: str, now: int) -> None:
        self.repository.mark_checked(token_hash, now)
        self.repository.commit()

    def end(self, token_hash: str) -> None:
        self.repository.remove(token_hash)
        self.repository.commit()

    async def sign_out(self, token: str) -> None:
        """The session is removed, and Jellyfin forgets its access token."""
        token_hash = fingerprint(token)
        stored = await anyio.to_thread.run_sync(
            self.repository.read, token_hash, int(self.clock.now())
        )
        await anyio.to_thread.run_sync(self.end, token_hash)
        if stored is None:
            return
        try:
            jellyfin_token = self.box.open(sealed_name(token_hash), stored.jellyfin_token)
        except SecretUnreadableError:
            return
        await self.forget_jellyfin(
            await self.address.jellyfin_url(), jellyfin_token, stored.device_id
        )

    async def forget_jellyfin(self, url: str | None, token: str, device_id: str) -> None:
        """Best effort: a failure leaves the access token to Jellyfin, which shelfdrop no
        longer holds."""
        try:
            await self.jellyfin.sign_out(url, token, device_id)
        except ServiceError as exc:
            logger.info("Jellyfin sign-out failed", extra={"error": str(exc)})
