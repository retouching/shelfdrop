"""Fakes of the internal account: its table in memory, and a Jellyfin of the settings."""

from dataclasses import replace
from typing import override

from shelfdrop.accounts.gate import SetupGate
from shelfdrop.accounts.repository import AccountRepository
from shelfdrop.accounts.service import AccountService
from shelfdrop.accounts.types import StoredAccount
from tests.unit.support import no_session
from tests.unit.works.support import FixedClock


class FakeAccountRepository(AccountRepository):
    """The one row in memory; it counts the commits."""

    def __init__(self, account: StoredAccount | None = None) -> None:
        super().__init__(no_session())
        self.account = account
        self.commits = 0

    @override
    def read(self) -> StoredAccount | None:
        return self.account

    @override
    def create(self, account: StoredAccount) -> bool:
        if self.account is not None:
            return False
        self.account = account
        self.commits += 1
        return True

    @override
    def save_password(self, password_hash: str, now: int) -> None:
        assert self.account is not None
        self.account = replace(self.account, password_hash=password_hash, password_changed_at=now)

    @override
    def finish_setup(self, now: int) -> None:
        assert self.account is not None
        self.account = replace(self.account, setup_finished_at=now)

    @override
    def commit(self) -> None:
        self.commits += 1


class FakeSetupJellyfin:
    """The Jellyfin of the settings: an address saved or not, and whether its test passes."""

    def __init__(self, url: str | None = None, *, connected: bool = False) -> None:
        self.url = url
        self.connected = connected
        self.tests = 0

    async def jellyfin_url(self) -> str | None:
        return self.url

    async def jellyfin_connected(self) -> bool:
        self.tests += 1
        return self.connected


def new_accounts(
    account: StoredAccount | None = None, jellyfin: FakeSetupJellyfin | None = None
) -> tuple[AccountService, FakeAccountRepository, FakeSetupJellyfin, SetupGate]:
    repository = FakeAccountRepository(account)
    jellyfin = jellyfin or FakeSetupJellyfin()
    gate = SetupGate()
    return AccountService(repository, jellyfin, gate, FixedClock()), repository, jellyfin, gate
