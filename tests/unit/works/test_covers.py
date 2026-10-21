"""shelfdrop.works.covers: the cover of a work kept from a search, read at its source."""

from typing import override

import httpx
import pytest

from shelfdrop.works.covers import WorkCovers
from shelfdrop.works.repository import WorkRepository
from shelfdrop.works.types import Work
from tests.unit.support import no_session
from tests.unit.works.support import FixedClock

JPEG = b"\xff\xd8\xff\xe0cover"


class KeptWorks(WorkRepository):
    def __init__(self, works: dict[str, Work]) -> None:
        super().__init__(no_session())
        self.works = works

    @override
    def read_work(self, work_id: str, now: int) -> Work | None:
        return self.works.get(work_id)

    @override
    def close(self) -> None:
        pass


def work(cover_url: str | None) -> Work:
    return Work(
        id="mangaupdates:1",
        title="Berserk",
        shelf_name="Berserk",
        authors=(),
        year=None,
        volumes=None,
        volumes_fr=None,
        form="manga",
        names=(),
        sources=("mangaupdates",),
        cover_url=cover_url,
        isbns=(),
        links={},
    )


def answer(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/cover.jpg":
        return httpx.Response(200, content=JPEG, headers={"Content-Type": "image/jpeg"})
    if request.url.path == "/page.html":
        return httpx.Response(200, content=b"<html>", headers={"Content-Type": "image/jpeg"})
    return httpx.Response(404)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_cover_of_a_work_kept_is_read_and_anything_else_is_none() -> None:
    works = {
        "mangaupdates:1": work("https://cdn.test/cover.jpg"),
        "mangaupdates:2": work("https://cdn.test/page.html"),
        "mangaupdates:3": work(None),
    }
    covers = WorkCovers(
        lambda: KeptWorks(works),
        httpx.AsyncClient(transport=httpx.MockTransport(answer)),
        FixedClock(),
    )

    assert await covers.cover("mangaupdates:1") == JPEG
    assert await covers.cover("mangaupdates:2") is None
    assert await covers.cover("mangaupdates:3") is None
    assert await covers.cover("mangaupdates:9") is None
