"""shelfdrop.modules.works.router: the cover of a work, kept a day by the browser, and a 404
without one."""

from typing import override

import pytest

from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode
from shelfdrop.modules.works.router import read_work_cover
from shelfdrop.modules.works.schemas import NameRead
from shelfdrop.works.covers import WorkCovers
from shelfdrop.works.types import NameChoice

WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


class FixedCovers(WorkCovers):
    """The covers of a few works, without a source nor a database."""

    def __init__(self, covers: dict[str, bytes]) -> None:
        self.covers = covers
        self.asked: list[str] = []

    @override
    async def cover(self, work_id: str) -> bytes | None:
        self.asked.append(work_id)
        return self.covers.get(work_id)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_cover_of_a_work_is_its_picture_kept_a_day() -> None:
    covers = FixedCovers({"bnf:http://catalogue.bnf.fr/ark:/12148/cb1": WEBP})

    response = await read_work_cover(covers, "bnf:http://catalogue.bnf.fr/ark:/12148/cb1")

    assert (response.status_code, response.media_type, response.body) == (200, "image/webp", WEBP)
    assert response.headers["Cache-Control"] == "private, max-age=86400"


@pytest.mark.anyio
@pytest.mark.parametrize("data", [None, b"<html>not a picture</html>"])
async def test_a_work_without_a_picture_is_a_404(data: bytes | None) -> None:
    covers = FixedCovers({} if data is None else {"anilist:1": data})

    with pytest.raises(ApiError) as raised:
        await read_work_cover(covers, "anilist:1")

    assert (raised.value.status_code, raised.value.code) == (404, ErrorCode.WORK_COVER_NOT_FOUND)


def test_a_name_answers_its_sources_and_the_most_trusted_of_them() -> None:
    kept = NameChoice(title="Gunnm", language="ja-ro", checked=True, sources=("kitsu", "bnf"))
    older = NameChoice(title="Gunnm", language="ja-ro", checked=True)

    assert NameRead.model_validate(kept).model_dump() == {
        "title": "Gunnm",
        "language": "ja-ro",
        "checked": True,
        "sources": ["kitsu", "bnf"],
        "source": "kitsu",
    }
    assert (NameRead.model_validate(older).sources, NameRead.model_validate(older).source) == (
        [],
        None,
    )
