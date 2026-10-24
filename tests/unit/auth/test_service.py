"""shelfdrop.auth.service: the sign-in of an administrator, the sessions and their check with
Jellyfin."""

import hashlib
from typing import override

import httpx
import pytest

from shelfdrop.accounts.service import AccountService
from shelfdrop.auth.exceptions import (
    JellyfinUnavailableError,
    LoginRefusedError,
    NotSignedInError,
    TooManyAttemptsError,
)
from shelfdrop.auth.repository import SessionRepository
from shelfdrop.auth.service import CHECK_SECONDS, SESSION_SECONDS, AuthService
from shelfdrop.auth.throttle import LoginThrottle
from shelfdrop.auth.types import StoredSession
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.settings.cipher import SecretBox
from tests.unit.accounts.support import new_accounts
from tests.unit.clients.support import URL, FakeJellyfin, user_dto
from tests.unit.settings.support import TEST_SECRET_KEY, FakeSettingsReader
from tests.unit.support import FakeJournal, no_session
from tests.unit.works.support import FixedClock


class FakeSessionRepository(SessionRepository):
    def __init__(self) -> None:
        super().__init__(no_session())
        self.rows: dict[str, StoredSession] = {}
        self.commits = 0

    @override
    def read(self, token_hash: str, now: int) -> StoredSession | None:
        found = self.rows.get(token_hash)
        return found if found is not None and found.expires_at > now else None

    @override
    def add(self, stored: StoredSession) -> None:
        self.rows[stored.token_hash] = stored

    @override
    def mark_checked(self, token_hash: str, now: int) -> None:
        found = self.rows[token_hash]
        self.rows[token_hash] = StoredSession(**{**found.__dict__, "checked_at": now})

    @override
    def remove(self, token_hash: str) -> None:
        self.rows.pop(token_hash, None)

    @override
    def remove_account_sessions(self, user_id: str, *, keep: str) -> None:
        self.rows = {
            k: v for k, v in self.rows.items() if v.account.user_id != user_id or k == keep
        }

    @override
    def remove_expired(self, now: int) -> None:
        self.rows = {k: v for k, v in self.rows.items() if v.expires_at > now}

    @override
    def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def accounts() -> dict[str, tuple[str, dict[str, object]]]:
    return {
        "sylvain": ("pw", user_dto("u1", "Sylvain", admin=True)),
        "reader": ("pw", user_dto("u2", "Reader", admin=False)),
        "gone": ("pw", user_dto("u3", "Gone", admin=True, disabled=True)),
    }


def new_service(
    jellyfin: FakeJellyfin | None = None,
    url: str | None = URL,
    internal: AccountService | None = None,
) -> tuple[AuthService, FakeSessionRepository, FakeJellyfin, FixedClock]:
    jellyfin = jellyfin or FakeJellyfin(accounts=accounts())
    internal = internal or new_accounts()[0]
    repository = FakeSessionRepository()
    clock = FixedClock()
    service = AuthService(
        repository,
        JellyfinClient(httpx.AsyncClient(transport=httpx.MockTransport(jellyfin)), "0.3.0"),
        FakeSettingsReader({"jellyfin.url": url}),
        SecretBox(TEST_SECRET_KEY),
        LoginThrottle(),
        clock,
        FakeJournal(),
        internal,
    )
    return service, repository, jellyfin, clock


def journal_of(service: AuthService) -> FakeJournal:
    assert isinstance(service.events, FakeJournal)
    return service.events


@pytest.mark.anyio
async def test_an_administrator_signs_in_and_only_the_fingerprint_is_kept() -> None:
    service, repository, _, clock = new_service()

    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")

    assert signed_in.account.username == "Sylvain"
    assert len(signed_in.token) >= 43  # 32 random bytes, base64url
    assert signed_in.expires_at == int(clock.now()) + SESSION_SECONDS
    [stored] = repository.rows.values()
    assert stored.token_hash == hashlib.sha256(signed_in.token.encode()).hexdigest()
    assert signed_in.token not in repr(stored)
    assert b"token-1" not in stored.jellyfin_token
    assert (await service.check(signed_in.token)).user_id == "u1"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("username", "password"), [("reader", "pw"), ("gone", "pw"), ("sylvain", "x"), ("nobody", "pw")]
)
async def test_every_refusal_is_the_same(username: str, password: str) -> None:
    service, repository, jellyfin, _ = new_service()

    with pytest.raises(LoginRefusedError):
        await service.sign_in(username, password, "10.0.0.1")

    assert repository.rows == {}
    # The session Jellyfin opened for a refused account is closed at once.
    assert jellyfin.tokens == {}


@pytest.mark.anyio
async def test_jellyfin_down_or_not_set_is_no_refusal() -> None:
    down, _, jellyfin, _ = new_service()
    jellyfin.down = True
    unset, _, _, _ = new_service(url=None)

    with pytest.raises(JellyfinUnavailableError):
        await down.sign_in("sylvain", "pw", "10.0.0.1")
    with pytest.raises(JellyfinUnavailableError):
        await unset.sign_in("sylvain", "pw", "10.0.0.1")


@pytest.mark.anyio
async def test_the_sixth_attempt_of_a_minute_is_not_sent() -> None:
    service, _, jellyfin, _ = new_service()
    for _ in range(5):
        with pytest.raises(LoginRefusedError):
            await service.sign_in("sylvain", "x", "10.0.0.1")

    with pytest.raises(TooManyAttemptsError):
        await service.sign_in("sylvain", "pw", "10.0.0.1")
    assert len(jellyfin.requests) == 5


@pytest.mark.anyio
async def test_jellyfin_confirms_the_session_every_five_minutes() -> None:
    service, _, jellyfin, clock = new_service()
    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")

    clock.at += CHECK_SECONDS - 1
    await service.check(signed_in.token)
    asked_before = jellyfin.paths().count("/Users/Me")
    clock.at += 1
    await service.check(signed_in.token)
    await service.check(signed_in.token)

    assert asked_before == 0
    assert jellyfin.paths().count("/Users/Me") == 1


@pytest.mark.anyio
async def test_a_session_jellyfin_revoked_ends() -> None:
    service, repository, jellyfin, clock = new_service()
    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")
    jellyfin.tokens.clear()
    clock.at += CHECK_SECONDS

    with pytest.raises(NotSignedInError):
        await service.check(signed_in.token)
    assert repository.rows == {}


@pytest.mark.anyio
async def test_an_account_no_longer_administrator_is_signed_out() -> None:
    jellyfin = FakeJellyfin(accounts=accounts())
    service, repository, _, clock = new_service(jellyfin)
    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")
    jellyfin.accounts["sylvain"] = ("pw", user_dto("u1", "Sylvain", admin=False))
    clock.at += CHECK_SECONDS

    with pytest.raises(NotSignedInError):
        await service.check(signed_in.token)
    assert repository.rows == {}


@pytest.mark.anyio
async def test_jellyfin_down_refuses_the_check_but_keeps_the_session() -> None:
    service, repository, jellyfin, clock = new_service()
    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")
    jellyfin.down = True
    clock.at += CHECK_SECONDS

    with pytest.raises(NotSignedInError):
        await service.check(signed_in.token)
    jellyfin.down = False
    assert (await service.check(signed_in.token)).username == "Sylvain"
    assert len(repository.rows) == 1


@pytest.mark.anyio
async def test_a_session_expires_after_thirty_days() -> None:
    service, _, _, clock = new_service()
    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")
    clock.at += SESSION_SECONDS

    with pytest.raises(NotSignedInError):
        await service.check(signed_in.token)


@pytest.mark.anyio
async def test_an_unknown_token_is_not_signed_in() -> None:
    service, _, _, _ = new_service()

    with pytest.raises(NotSignedInError):
        await service.check("made-up")


@pytest.mark.anyio
async def test_a_sign_out_ends_the_session_here_and_in_jellyfin() -> None:
    service, repository, jellyfin, _ = new_service()
    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")

    await service.sign_out(signed_in.token)

    assert repository.rows == {}
    assert jellyfin.tokens == {}
    with pytest.raises(NotSignedInError):
        await service.check(signed_in.token)


@pytest.mark.anyio
async def test_a_sign_in_and_the_attempts_throttled_go_to_the_journal_without_a_name() -> None:
    service, _, _, _ = new_service()

    await service.sign_in("sylvain", "pw", "10.0.0.1", "FR")
    for _ in range(6):
        with pytest.raises((LoginRefusedError, TooManyAttemptsError)):
            await service.sign_in("guess-of-a-stranger", "x", "10.0.0.9", "DE")

    signed, refused = journal_of(service).events
    assert signed.facts == {"account": "Sylvain", "address": "10.0.0.1", "country": "FR"}
    assert refused.facts == {"refused": True, "address": "10.0.0.9", "country": "DE"}
    assert "guess-of-a-stranger" not in repr(refused)


INTERNAL_PASSWORD = "the-internal-password"


async def with_internal() -> tuple[AuthService, FakeSessionRepository, FakeJellyfin, FixedClock]:
    """A service whose internal account is `Admin`."""
    internal = new_accounts()[0]
    await internal.create("Admin", INTERNAL_PASSWORD, setup=False)
    return new_service(internal=internal)


@pytest.mark.anyio
async def test_the_internal_account_signs_in_without_asking_jellyfin() -> None:
    service, repository, jellyfin, clock = await with_internal()

    signed_in = await service.sign_in("admin", INTERNAL_PASSWORD, "10.0.0.1")

    assert (signed_in.account.username, signed_in.account.internal) == ("Admin", True)
    assert jellyfin.requests == []
    [stored] = repository.rows.values()
    assert (stored.jellyfin_token, stored.device_id) == (b"", "")
    clock.at += CHECK_SECONDS
    assert (await service.check(signed_in.token)).internal is True
    assert jellyfin.requests == []
    assert journal_of(service).of("login")[0].facts["account"] == "Admin"


@pytest.mark.anyio
async def test_a_wrong_password_of_the_internal_account_is_refused_without_jellyfin() -> None:
    service, repository, jellyfin, _ = await with_internal()

    with pytest.raises(LoginRefusedError):
        await service.sign_in("Admin", "pw", "10.0.0.1")

    assert jellyfin.requests == []
    assert repository.rows == {}


@pytest.mark.anyio
async def test_another_name_still_signs_in_through_jellyfin() -> None:
    service, _, jellyfin, _ = await with_internal()

    signed_in = await service.sign_in("sylvain", "pw", "10.0.0.1")

    assert (signed_in.account.username, signed_in.account.internal) == ("Sylvain", False)
    assert jellyfin.requests != []


@pytest.mark.anyio
async def test_the_internal_account_signs_in_while_jellyfin_is_not_set() -> None:
    internal = new_accounts()[0]
    await internal.create("Admin", INTERNAL_PASSWORD, setup=True)
    service, _, _, _ = new_service(url=None, internal=internal)

    assert (await service.sign_in("Admin", INTERNAL_PASSWORD, "10.0.0.1")).account.internal


@pytest.mark.anyio
async def test_a_new_password_ends_the_other_sessions_of_the_internal_account() -> None:
    service, repository, _, _ = await with_internal()
    kept = await service.sign_in("Admin", INTERNAL_PASSWORD, "10.0.0.1")
    other = await service.sign_in("Admin", INTERNAL_PASSWORD, "10.0.0.2")
    jellyfin_session = await service.sign_in("sylvain", "pw", "10.0.0.3")

    await service.end_other_internal_sessions(kept.token)

    assert len(repository.rows) == 2
    assert (await service.check(kept.token)).internal is True
    assert (await service.check(jellyfin_session.token)).username == "Sylvain"
    with pytest.raises(NotSignedInError):
        await service.check(other.token)
    await service.end_other_internal_sessions(None)
    with pytest.raises(NotSignedInError):
        await service.check(kept.token)


@pytest.mark.anyio
async def test_a_sign_out_of_the_internal_account_asks_jellyfin_nothing() -> None:
    service, repository, jellyfin, _ = await with_internal()
    signed_in = await service.sign_in("Admin", INTERNAL_PASSWORD, "10.0.0.1")

    await service.sign_out(signed_in.token)

    assert repository.rows == {}
    assert jellyfin.requests == []
