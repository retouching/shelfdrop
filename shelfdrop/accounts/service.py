"""AccountService: the internal account of shelfdrop (one administrator, without Jellyfin) and
the set-up of the first launch it opens (ADR 0024).

The password is kept as its scrypt alone; it is never logged. The hashes run in the threadpool:
each one takes about a tenth of a second.
"""

import logging
from typing import Protocol

import anyio
import anyio.to_thread

from shelfdrop.accounts.exceptions import (
    AccountExistsError,
    AccountMissingError,
    JellyfinNotConnectedError,
    PasswordRefusedError,
    SetupDoneError,
)
from shelfdrop.accounts.gate import SetupGate
from shelfdrop.accounts.repository import AccountRepository
from shelfdrop.accounts.rules import setup_needed
from shelfdrop.accounts.types import AccountView, SetupState, StoredAccount
from shelfdrop.utils.passwords import hash_password, verify_password
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)


class SetupJellyfin(Protocol):
    """The Jellyfin of the settings: its address saved, and the test of what is saved."""

    async def jellyfin_url(self) -> str | None: ...

    async def jellyfin_connected(self) -> bool: ...


def view_of(account: StoredAccount) -> AccountView:
    return AccountView(
        username=account.username,
        created_at=account.created_at,
        password_changed_at=account.password_changed_at,
    )


class AccountService:
    def __init__(
        self,
        repository: AccountRepository,
        jellyfin: SetupJellyfin,
        gate: SetupGate,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.jellyfin = jellyfin
        self.gate = gate
        self.clock = clock

    async def read(self) -> AccountView | None:
        account = await anyio.to_thread.run_sync(self.repository.read)
        return None if account is None else view_of(account)

    async def setup_needed(self) -> bool:
        """Read again until the set-up is known finished, then kept in memory."""
        if self.gate.done:
            return False
        account = await anyio.to_thread.run_sync(self.repository.read)
        needed = setup_needed(account, await self.jellyfin.jellyfin_url())
        if not needed:
            self.gate.done = True
        return needed

    async def setup_state(self) -> SetupState:
        needed = await self.setup_needed()
        account = await anyio.to_thread.run_sync(self.repository.read)
        return SetupState(needed=needed, account=account is not None)

    async def create(self, username: str, password: str, *, setup: bool) -> AccountView:
        """The internal account. `setup`: the first step of the set-up, allowed only while it
        is needed, and the set-up stays open; otherwise (the settings) it is finished at once.
        Raises SetupDoneError and AccountExistsError."""
        if setup and not await self.setup_needed():
            raise SetupDoneError
        now = int(self.clock.now())
        account = StoredAccount(
            username=username.strip(),
            password_hash=await anyio.to_thread.run_sync(hash_password, password),
            created_at=now,
            password_changed_at=now,
            setup_finished_at=None if setup else now,
        )
        if not await anyio.to_thread.run_sync(self.repository.create, account):
            raise AccountExistsError
        logger.info("Internal account created", extra={"account": account.username})
        return view_of(account)

    async def change_password(self, current: str, new: str) -> AccountView:
        """Raises AccountMissingError and PasswordRefusedError."""
        account = await anyio.to_thread.run_sync(self.repository.read)
        if account is None:
            raise AccountMissingError
        if not await anyio.to_thread.run_sync(verify_password, current, account.password_hash):
            logger.info("Password change refused")
            raise PasswordRefusedError
        now = int(self.clock.now())
        password_hash = await anyio.to_thread.run_sync(hash_password, new)
        await anyio.to_thread.run_sync(self.save_password, password_hash, now)
        logger.info("Password changed", extra={"account": account.username})
        return AccountView(
            username=account.username,
            created_at=account.created_at,
            password_changed_at=now,
        )

    def save_password(self, password_hash: str, now: int) -> None:
        self.repository.save_password(password_hash, now)
        self.repository.commit()

    async def finish_setup(self) -> None:
        """The set-up ends once the Jellyfin saved answers its test. Raises SetupDoneError,
        AccountMissingError and JellyfinNotConnectedError."""
        if not await self.setup_needed():
            raise SetupDoneError
        account = await anyio.to_thread.run_sync(self.repository.read)
        if account is None:
            raise AccountMissingError
        if not await self.jellyfin.jellyfin_connected():
            raise JellyfinNotConnectedError
        await anyio.to_thread.run_sync(self.mark_finished, int(self.clock.now()))
        self.gate.done = True
        logger.info("Set-up finished")

    def mark_finished(self, now: int) -> None:
        self.repository.finish_setup(now)
        self.repository.commit()

    async def internal_name(self) -> str | None:
        """The name of the internal account, None without one (the sign-in)."""
        account = await anyio.to_thread.run_sync(self.repository.read)
        return None if account is None else account.username

    async def verify(self, password: str) -> bool:
        """Whether `password` is the one of the internal account."""
        account = await anyio.to_thread.run_sync(self.repository.read)
        if account is None:
            return False
        return await anyio.to_thread.run_sync(verify_password, password, account.password_hash)
