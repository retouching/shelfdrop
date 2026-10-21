"""shelfdrop.clients.discord: a message posted on a webhook, its picture, a 429."""

import httpx
import pytest

from shelfdrop.clients.discord import DiscordClient, RateLimitedError
from shelfdrop.clients.exceptions import ServiceError, ServiceNotConfiguredError
from tests.unit.clients.support import FakeDiscord


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_client(discord: FakeDiscord) -> DiscordClient:
    return DiscordClient(httpx.AsyncClient(transport=httpx.MockTransport(discord)))


@pytest.mark.anyio
async def test_a_message_is_posted_as_json_and_waited_for() -> None:
    discord = FakeDiscord()

    await new_client(discord).post(FakeDiscord.WEBHOOK, {"embeds": [{"title": "Rangé"}]})

    assert discord.messages == [({"embeds": [{"title": "Rangé"}]}, None)]
    assert discord.requests[0].url.params["wait"] == "true"


@pytest.mark.anyio
async def test_a_picture_goes_with_the_payload_in_a_multipart_body() -> None:
    discord = FakeDiscord()
    payload = {"embeds": [{"thumbnail": {"url": "attachment://cover.jpg"}}]}

    await new_client(discord).post(
        FakeDiscord.WEBHOOK, payload, ("cover.jpg", b"\xff\xd8", "image/jpeg")
    )

    assert discord.messages == [(payload, b"\xff\xd8")]


@pytest.mark.anyio
async def test_a_429_gives_the_seconds_to_wait_and_an_error_its_status() -> None:
    discord = FakeDiscord(limited=1, fails=1)
    client = new_client(discord)

    with pytest.raises(RateLimitedError) as limited:
        await client.post(FakeDiscord.WEBHOOK, {})
    with pytest.raises(ServiceError) as failed:
        await client.post(FakeDiscord.WEBHOOK, {})

    assert limited.value.retry_after == 0.01
    assert failed.value.status == 500
    assert FakeDiscord.WEBHOOK not in str(failed.value)


@pytest.mark.anyio
async def test_without_a_webhook_nothing_is_posted() -> None:
    discord = FakeDiscord()

    with pytest.raises(ServiceNotConfiguredError):
        await new_client(discord).post(None, {})
    assert discord.requests == []
