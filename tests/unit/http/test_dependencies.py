"""shelfdrop.http.dependencies: who asks, by the session or by an access token."""

import pytest
from starlette.requests import Request

from shelfdrop.http.dependencies import bearer_of, check_bearer
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.tokens.service import TokenService
from shelfdrop.tokens.throttle import TOKEN_LIMIT, TokenThrottle
from tests.unit.tokens.support import FakeTokenRepository
from tests.unit.works.support import FixedClock


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def request_with(*headers: tuple[bytes, bytes]) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": list(headers)})


@pytest.mark.parametrize(
    ("header", "secret"),
    [
        (None, None),
        (b"Bearer sd_abc", "sd_abc"),
        (b"bearer  sd_abc ", "sd_abc"),
        (b"Basic dXNlcjpwYXNz", ""),
        (b"Bearer", ""),
    ],
)
def test_the_secret_of_a_bearer_header(header: bytes | None, secret: str | None) -> None:
    request = request_with() if header is None else request_with((b"authorization", header))

    assert bearer_of(request) == secret


@pytest.mark.anyio
async def test_a_token_acts_under_its_name_and_reads_with_any_scope() -> None:
    service = TokenService(FakeTokenRepository(), TokenThrottle(), FixedClock())
    reader = await service.create("Grafana", "read", None, "sylvain")
    writer = await service.create("Hermes", "write", None, "sylvain")

    assert (await check_bearer(reader.secret, service, "read")).username == "Grafana"
    assert (await check_bearer(writer.secret, service, "write")).username == "Hermes"


@pytest.mark.anyio
async def test_a_token_of_reading_never_writes() -> None:
    service = TokenService(FakeTokenRepository(), TokenThrottle(), FixedClock())
    reader = await service.create("Grafana", "read", None, "sylvain")

    with pytest.raises(ApiError) as caught:
        await check_bearer(reader.secret, service, "write")

    assert (caught.value.status_code, caught.value.code) == (403, "token_forbidden")


@pytest.mark.anyio
async def test_a_token_refused_is_a_401_and_one_too_busy_a_429() -> None:
    service = TokenService(FakeTokenRepository(), TokenThrottle(), FixedClock())
    created = await service.create("Hermes", "write", None, "sylvain")
    for _ in range(TOKEN_LIMIT):
        await check_bearer(created.secret, service, "read")

    with pytest.raises(ApiError) as busy:
        await check_bearer(created.secret, service, "read")
    with pytest.raises(ApiError) as refused:
        await check_bearer("sd_unknown", service, "read")

    assert (busy.value.status_code, busy.value.code) == (429, "too_many_requests")
    assert (refused.value.status_code, refused.value.code) == (401, "not_signed_in")
