"""shelfdrop.clients.jellyfin: the requests of Jellyfin, in the shape of its API."""

import json
from collections.abc import AsyncIterator

import httpx
import pytest

from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from shelfdrop.clients.jellyfin import JellyfinClient
from tests.unit.clients.support import ADMIN_ID, API_KEY, URL, FakeJellyfin, user_dto


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


def book(item_id: str, path: str, **fields: object) -> dict[str, object]:
    return {
        "Id": item_id,
        "Type": "Book",
        "Name": item_id,
        "Path": path,
        "LibraryId": "lib-1",
        **fields,
    }


@pytest.mark.anyio
async def test_the_libraries_give_their_item_their_folders_and_their_scan() -> None:
    jellyfin = FakeJellyfin(
        libraries=[
            {
                "Name": "BD & Mangas",
                "CollectionType": "books",
                "Locations": ["/files/comics"],
                "ItemId": "lib-1",
                "RefreshProgress": 42.5,
                "RefreshStatus": "Active",
            },
            {
                "Name": "Livres",
                "CollectionType": "books",
                "Locations": [],
                "ItemId": "lib-2",
                "RefreshProgress": 100,
                "RefreshStatus": "Idle",
            },
        ]
    )

    comics, books = await new_client(jellyfin).libraries(URL, API_KEY)

    assert (comics.item_id, comics.locations, comics.refresh_progress) == (
        "lib-1",
        ("/files/comics",),
        42.5,
    )
    assert books.refresh_progress is None


@pytest.mark.anyio
async def test_the_items_of_a_library_are_read_with_their_fields() -> None:
    jellyfin = FakeJellyfin(
        items={
            "b1": book(
                "b1",
                "/files/comics/Berserk/Berserk - T01.cbz",
                Overview="Guts.",
                Genres=["Seinen"],
                People=[
                    {"Name": "Kentaro Miura", "Type": "Author"},
                    {"Name": "X", "Type": "Editor"},
                ],
                ProductionYear=1990,
                ImageTags={"Primary": "abc"},
                IndexNumber=1,
            ),
            "f1": {"Id": "f1", "Type": "Folder", "Name": "Berserk", "LibraryId": "lib-1"},
        }
    )

    [item] = await new_client(jellyfin).items(URL, API_KEY, "lib-1", ["Book", "AudioBook"])

    assert item.path == "/files/comics/Berserk/Berserk - T01.cbz"
    assert (item.overview, item.genres, item.authors, item.year) == (
        "Guts.",
        ("Seinen",),
        ("Kentaro Miura",),
        1990,
    )
    assert item.has_image
    assert item.index_number == 1
    request = jellyfin.requests[0]
    assert request.url.params["recursive"] == "true"
    assert "Path" in request.url.params["fields"]


@pytest.mark.anyio
async def test_an_item_is_read_whole_and_written_back() -> None:
    jellyfin = FakeJellyfin(items={"b1": book("b1", "/files/x.cbz", Genres=["Seinen"])})
    client = new_client(jellyfin)

    body = await client.item(URL, API_KEY, "b1")
    await client.update_item(URL, API_KEY, "b1", {**body, "Name": "Berserk - T01"})

    assert jellyfin.items["b1"]["Name"] == "Berserk - T01"
    assert jellyfin.items["b1"]["Genres"] == ["Seinen"]
    read = next(r for r in jellyfin.requests if r.method == "GET" and r.url.path == "/Items/b1")
    assert read.url.params["userId"] == ADMIN_ID


@pytest.mark.anyio
async def test_an_item_is_read_as_the_first_administrator_not_disabled() -> None:
    jellyfin = FakeJellyfin(
        accounts={
            "kid": ("pw", user_dto("u1", "Kid", admin=False)),
            "old": ("pw", user_dto("u2", "Old", admin=True, disabled=True)),
            "sylvain": ("pw", user_dto("u3", "Sylvain", admin=True)),
        },
        administrator=False,
        items={"b1": book("b1", "/files/x.cbz")},
    )

    await new_client(jellyfin).item(URL, API_KEY, "b1")

    read = next(r for r in jellyfin.requests if r.url.path == "/Items/b1")
    assert read.url.params["userId"] == "u3"


@pytest.mark.anyio
async def test_an_item_without_an_administrator_is_a_service_error() -> None:
    jellyfin = FakeJellyfin(administrator=False, items={"b1": book("b1", "/files/x.cbz")})

    with pytest.raises(ServiceError):
        await new_client(jellyfin).item(URL, API_KEY, "b1")


@pytest.mark.anyio
async def test_an_image_is_sent_in_base64_and_read_as_bytes() -> None:
    jellyfin = FakeJellyfin(items={"b1": book("b1", "/files/x.cbz")})
    client = new_client(jellyfin)

    await client.set_image(URL, API_KEY, "b1", b"\xff\xd8jpeg", "image/jpeg")
    data, content_type = await client.image(URL, API_KEY, "b1", 600)

    sent = jellyfin.requests[0]
    assert sent.content == b"/9hqcGVn"
    assert sent.headers["Content-Type"] == "image/jpeg"
    assert (data, content_type) == (b"\xff\xd8jpeg", "image/jpeg")
    assert jellyfin.requests[1].url.params["maxWidth"] == "600"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("new", {"metadataRefreshMode": "Default", "imageRefreshMode": "Default"}),
        (
            "missing",
            {
                "metadataRefreshMode": "FullRefresh",
                "imageRefreshMode": "FullRefresh",
                "replaceAllMetadata": "false",
                "replaceAllImages": "false",
            },
        ),
        (
            "all",
            {
                "metadataRefreshMode": "FullRefresh",
                "imageRefreshMode": "FullRefresh",
                "replaceAllMetadata": "true",
                "replaceAllImages": "true",
            },
        ),
    ],
)
async def test_a_refresh_sends_the_modes_of_its_scan(mode: str, expected: dict[str, str]) -> None:
    jellyfin = FakeJellyfin(items={"lib-1": {"Id": "lib-1", "Type": "CollectionFolder"}})
    client = new_client(jellyfin)

    await client.refresh(URL, API_KEY, "lib-1", mode)
    await client.refresh_libraries(URL, API_KEY)

    assert jellyfin.refreshed == [("lib-1", {"recursive": "true", **expected}), ("library", {})]


@pytest.mark.anyio
async def test_a_file_is_streamed_as_jellyfin_sends_it_and_closed_at_its_end() -> None:
    data = bytes(range(256)) * 300
    jellyfin = FakeJellyfin(items={"b1": book("b1", "/files/x.cbz")}, files={"b1": data})
    client = new_client(jellyfin)

    read = await client.download(URL, API_KEY, "b1")
    chunks = [chunk async for chunk in read.chunks]

    assert b"".join(chunks) == data
    assert (read.content_type, read.size) == ("application/octet-stream", len(data))
    [request] = jellyfin.requests
    assert request.url.path == "/Items/b1/Download"
    assert API_KEY in request.headers["Authorization"]


@pytest.mark.anyio
async def test_a_file_jellyfin_does_not_have_is_a_service_error_with_its_status() -> None:
    jellyfin = FakeJellyfin(items={"b1": book("b1", "/files/x.cbz")})

    with pytest.raises(ServiceError) as refused:
        await new_client(jellyfin).download(URL, API_KEY, "b1")

    assert refused.value.status == 404
    with pytest.raises(ServiceNotConfiguredError):
        await new_client(jellyfin).download(URL, None, "b1")


@pytest.mark.anyio
async def test_the_size_of_a_file_is_the_total_of_its_first_byte() -> None:
    jellyfin = FakeJellyfin(items={"b1": book("b1", "/files/x.cbz")}, files={"b1": b"x" * 4096})
    client = new_client(jellyfin)

    assert await client.file_size(URL, API_KEY, "b1") == 4096
    assert jellyfin.requests[0].headers["Range"] == "bytes=0-0"
    # The range not taken: the length of the whole file, never read.
    whole = httpx.MockTransport(
        lambda r: httpx.Response(200, content=b"abc", headers={"Content-Length": "3"})
    )
    assert (
        await JellyfinClient(httpx.AsyncClient(transport=whole), "0.3.0").file_size(
            URL, API_KEY, "b1"
        )
        == 3
    )
    # Unknown: None, never an error.
    assert await client.file_size(URL, API_KEY, "nope") is None
    jellyfin.down = True
    assert await client.file_size(URL, API_KEY, "b1") is None


@pytest.mark.anyio
async def test_an_item_read_with_its_administrator_asks_no_users() -> None:
    jellyfin = FakeJellyfin(items={"b1": book("b1", "/files/x.cbz")})

    await new_client(jellyfin).item(URL, API_KEY, "b1", ADMIN_ID)

    assert jellyfin.paths() == ["/Items/b1"]


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"first"
        raise httpx.ReadError("cut")


@pytest.mark.anyio
async def test_a_file_cut_on_the_way_is_a_service_error() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200, stream=BrokenStream()))
    client = JellyfinClient(httpx.AsyncClient(transport=transport), "0.3.0")

    read = await client.download(URL, API_KEY, "b1")

    with pytest.raises(ServiceError):
        async for _ in read.chunks:
            pass
