"""shelfdrop.tokens.service: the access tokens, created once, checked, counted, revoked."""

import hashlib

import pytest

from shelfdrop.tokens.exceptions import (
    TokenNotFoundError,
    TokenRefusedError,
    TokenThrottledError,
)
from shelfdrop.tokens.service import DAY_SECONDS, USE_SECONDS, TokenService
from shelfdrop.tokens.throttle import TOKEN_LIMIT, TokenThrottle
from tests.unit.tokens.support import FakeTokenRepository
from tests.unit.works.support import FixedClock


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_service() -> tuple[TokenService, FakeTokenRepository, FixedClock]:
    repository = FakeTokenRepository()
    clock = FixedClock()
    return TokenService(repository, TokenThrottle(), clock), repository, clock


@pytest.mark.anyio
async def test_a_token_keeps_the_fingerprint_of_its_secret_alone() -> None:
    service, repository, clock = new_service()

    created = await service.create("Hermes", "write", 90, "sylvain")

    assert created.secret.startswith("sd_")
    assert len(created.secret) > 40
    kept, token, _ = repository.rows[created.token.id]
    assert kept == hashlib.sha256(created.secret.encode()).hexdigest()
    assert created.secret not in repr(repository.rows)
    assert token.expires_at == int(clock.now()) + 90 * DAY_SECONDS
    assert repository.audit == [(int(clock.now()), "sylvain", "created", "token.1")]
    assert repository.commits == 1


@pytest.mark.anyio
async def test_two_tokens_never_share_a_secret_and_one_may_last_forever() -> None:
    service, _, _ = new_service()

    first = await service.create("Hermes", "read", None, "sylvain")
    second = await service.create("Hermes", "read", None, "sylvain")

    assert first.secret != second.secret
    assert first.token.expires_at is None


@pytest.mark.anyio
async def test_a_token_checked_gives_its_name_and_its_scope_and_its_last_use() -> None:
    service, repository, clock = new_service()
    created = await service.create("Hermes", "read", 30, "sylvain")

    checked = await service.check(created.secret)

    assert (checked.name, checked.scope) == ("Hermes", "read")
    assert repository.rows[created.token.id][1].last_used_at == int(clock.now())


@pytest.mark.anyio
async def test_the_last_use_is_written_once_a_minute() -> None:
    service, repository, clock = new_service()
    created = await service.create("Hermes", "read", 30, "sylvain")
    await service.check(created.secret)
    commits = repository.commits

    clock.at += USE_SECONDS - 1
    await service.check(created.secret)
    assert repository.commits == commits
    clock.at += 1
    await service.check(created.secret)
    assert repository.commits == commits + 1


@pytest.mark.anyio
@pytest.mark.parametrize("secret", ["", "sd_unknown", "not-a-token"])
async def test_an_unknown_secret_is_refused(secret: str) -> None:
    service, _, _ = new_service()
    await service.create("Hermes", "read", 30, "sylvain")

    with pytest.raises(TokenRefusedError):
        await service.check(secret)


@pytest.mark.anyio
async def test_an_expired_token_is_refused() -> None:
    service, _, clock = new_service()
    created = await service.create("Hermes", "read", 30, "sylvain")

    clock.at += 30 * DAY_SECONDS

    with pytest.raises(TokenRefusedError):
        await service.check(created.secret)


@pytest.mark.anyio
async def test_a_token_revoked_is_refused_at_once_and_leaves_the_list() -> None:
    service, repository, clock = new_service()
    kept = await service.create("Grafana", "read", None, "sylvain")
    created = await service.create("Hermes", "write", None, "sylvain")
    await service.check(created.secret)

    await service.revoke(created.token.id, "sylvain")

    with pytest.raises(TokenRefusedError):
        await service.check(created.secret)
    assert [t.name for t in await service.read_all()] == [kept.token.name]
    assert repository.audit[-1] == (int(clock.now()), "sylvain", "revoked", "token.2")


@pytest.mark.anyio
async def test_a_token_unknown_or_revoked_already_cannot_be_revoked() -> None:
    service, _, _ = new_service()
    created = await service.create("Hermes", "write", None, "sylvain")
    await service.revoke(created.token.id, "sylvain")

    with pytest.raises(TokenNotFoundError):
        await service.revoke(created.token.id, "sylvain")
    with pytest.raises(TokenNotFoundError):
        await service.revoke(99, "sylvain")


@pytest.mark.anyio
async def test_a_token_makes_60_requests_a_minute() -> None:
    service, _, clock = new_service()
    created = await service.create("Hermes", "read", None, "sylvain")
    other = await service.create("Grafana", "read", None, "sylvain")
    for _ in range(TOKEN_LIMIT):
        await service.check(created.secret)

    with pytest.raises(TokenThrottledError):
        await service.check(created.secret)
    await service.check(other.secret)
    clock.at += 60
    await service.check(created.secret)
