"""shelfdrop.clients.jellyfin: the requests of Jellyfin, in the shape of its API."""

import json

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.jellyfin import JellyfinClient
from tests.unit.clients.support import API_KEY, URL, FakeJellyfin, user_dto


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_client(jellyfin: FakeJellyfin) -> JellyfinClient:
    return JellyfinClient(httpx.AsyncClient(transport=httpx.MockTransport(jellyfin)), "0.3.0")


@pytest.mark.anyio
async def test_a_sign_in_sends_the_credentials_in_the_body_alone() -> None:
    jellyfin = FakeJellyfin(accounts={"sylvain": ("pw", user_dto("u1", "Sylvain", admin=True))})

    login = await new_client(jellyfin).authenticate(URL, "sylvain", "pw", "device-1")

    [request] = jellyfin.requests
    assert request.method == "POST"
    assert request.url == f"{URL}/Users/AuthenticateByName"
    assert json.loads(request.content) == {"Username": "sylvain", "Pw": "pw"}
    assert request.headers["Authorization"] == (
        'MediaBrowser Client="shelfdrop", Device="shelfdrop", DeviceId="device-1", Version="0.3.0"'
    )
    assert login.user.id == "u1"
    assert login.user.name == "Sylvain"
    assert login.user.administrator is True
    assert login.token == "token-1"


@pytest.mark.anyio
async def test_wrong_credentials_are_refused() -> None:
    jellyfin = FakeJellyfin(accounts={"sylvain": ("pw", user_dto("u1", "Sylvain", admin=True))})

    with pytest.raises(ServiceError) as refused:
        await new_client(jellyfin).authenticate(URL, "sylvain", "wrong", "d")

    assert refused.value.refused


@pytest.mark.anyio
async def test_the_session_is_read_and_ended_with_its_token() -> None:
    jellyfin = FakeJellyfin(accounts={"sylvain": ("pw", user_dto("u1", "Sylvain", admin=True))})
    client = new_client(jellyfin)
    login = await client.authenticate(URL, "sylvain", "pw", "d")

    user = await client.current_user(URL, login.token, "d")
    await client.sign_out(URL, login.token, "d")

    assert user.name == "Sylvain"
    assert 'Token="token-1"' in jellyfin.requests[1].headers["Authorization"]
    with pytest.raises(ServiceError) as refused:
        await client.current_user(URL, login.token, "d")
    assert refused.value.refused


@pytest.mark.anyio
async def test_the_server_and_its_libraries_are_read_with_the_api_key() -> None:
    jellyfin = FakeJellyfin(
        libraries=[
            {"Name": "BD & Mangas", "CollectionType": "books", "Locations": ["/data/comics"]},
            {"Name": "Films", "CollectionType": "movies"},
        ]
    )
    client = new_client(jellyfin)

    version = await client.server_version(URL, API_KEY)
    libraries = await client.libraries(URL, API_KEY)

    assert version == "10.11.2"
    assert [(lib.name, lib.collection_type) for lib in libraries] == [
        ("BD & Mangas", "books"),
        ("Films", "movies"),
    ]
    assert f'Token="{API_KEY}"' in jellyfin.requests[0].headers["Authorization"]
    assert API_KEY not in str(jellyfin.requests[0].url)


@pytest.mark.anyio
async def test_without_address_or_key_nothing_is_asked() -> None:
    jellyfin = FakeJellyfin()
    client = new_client(jellyfin)

    with pytest.raises(ServiceNotConfiguredError):
        await client.server_version(None, API_KEY)
    with pytest.raises(ServiceNotConfiguredError):
        await client.server_version(URL, None)
    assert jellyfin.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "answer",
    [httpx.Response(503), httpx.Response(200, content=b"<html>"), httpx.Response(200, json={})],
)
async def test_a_failed_answer_is_a_service_error(answer: httpx.Response) -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: answer))

    with pytest.raises(ServiceError) as failed:
        await JellyfinClient(http, "0.3.0").current_user(URL, "t", "d")
    assert not failed.value.refused
