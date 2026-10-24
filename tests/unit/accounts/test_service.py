"""shelfdrop.accounts.service: the internal account, its password, and the set-up of the first
launch."""

import pytest

from shelfdrop.accounts.exceptions import (
    AccountExistsError,
    AccountMissingError,
    JellyfinNotConnectedError,
    PasswordRefusedError,
    SetupDoneError,
)
from tests.unit.accounts.support import FakeSetupJellyfin, new_accounts

PASSWORD = "a-password-of-the-tests"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_first_step_keeps_the_scrypt_alone_and_leaves_the_set_up_open() -> None:
    service, repository, _, gate = new_accounts()

    view = await service.create(" admin ", PASSWORD, setup=True)

    assert view.username == "admin"
    assert repository.account is not None
    assert repository.account.password_hash.startswith("scrypt$")
    assert PASSWORD not in repository.account.password_hash
    assert repository.account.setup_finished_at is None
    assert await service.setup_needed() is True
    assert gate.done is False
    assert await service.verify(PASSWORD) is True
    assert await service.verify("another-password") is False


@pytest.mark.anyio
async def test_the_first_step_is_refused_once_the_set_up_is_not_needed() -> None:
    service, repository, _, gate = new_accounts(jellyfin=FakeSetupJellyfin("http://jellyfin"))

    with pytest.raises(SetupDoneError):
        await service.create("admin", PASSWORD, setup=True)

    assert repository.account is None
    assert gate.done is True


@pytest.mark.anyio
async def test_a_second_account_is_refused_the_first_one_wins() -> None:
    service, repository, _, _ = new_accounts()
    await service.create("admin", PASSWORD, setup=True)

    with pytest.raises(AccountExistsError):
        await service.create("other", PASSWORD, setup=True)

    assert repository.account is not None
    assert repository.account.username == "admin"


@pytest.mark.anyio
async def test_an_account_created_from_the_settings_never_opens_the_set_up() -> None:
    service, repository, _, _ = new_accounts(jellyfin=FakeSetupJellyfin("http://jellyfin"))

    await service.create("admin", PASSWORD, setup=False)

    assert repository.account is not None
    assert repository.account.setup_finished_at is not None
    assert await service.setup_needed() is False


@pytest.mark.anyio
async def test_the_set_up_ends_only_with_jellyfin_connected() -> None:
    jellyfin = FakeSetupJellyfin()
    service, repository, _, gate = new_accounts(jellyfin=jellyfin)
    await service.create("admin", PASSWORD, setup=True)

    with pytest.raises(JellyfinNotConnectedError):
        await service.finish_setup()
    jellyfin.url, jellyfin.connected = "http://jellyfin", True
    assert await service.setup_needed() is True
    await service.finish_setup()

    assert repository.account is not None
    assert repository.account.setup_finished_at is not None
    assert gate.done is True
    assert (await service.setup_state()).needed is False
    with pytest.raises(SetupDoneError):
        await service.finish_setup()


@pytest.mark.anyio
async def test_the_set_up_cannot_end_without_its_account() -> None:
    service, _, jellyfin, _ = new_accounts(jellyfin=FakeSetupJellyfin(connected=True))

    with pytest.raises(AccountMissingError):
        await service.finish_setup()

    assert jellyfin.tests == 0


@pytest.mark.anyio
async def test_a_new_password_needs_the_current_one() -> None:
    service, repository, _, _ = new_accounts()
    await service.create("admin", PASSWORD, setup=False)
    before = repository.account

    with pytest.raises(PasswordRefusedError):
        await service.change_password("wrong-password", "a-new-password-0")
    assert repository.account == before
    await service.change_password(PASSWORD, "a-new-password-0")

    assert await service.verify("a-new-password-0") is True
    assert await service.verify(PASSWORD) is False


@pytest.mark.anyio
async def test_without_an_account_nothing_signs_in_nor_changes() -> None:
    service, _, _, _ = new_accounts()

    assert await service.internal_name() is None
    assert await service.verify(PASSWORD) is False
    assert await service.read() is None
    with pytest.raises(AccountMissingError):
        await service.change_password(PASSWORD, "a-new-password-0")
