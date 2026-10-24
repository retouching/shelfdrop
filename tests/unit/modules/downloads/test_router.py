"""shelfdrop.modules.downloads.router: the cover of the work of a download, for the page."""

import pytest

from shelfdrop.downloads.types import Choice, SendOrder
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.modules.downloads.router import read_download_cover
from shelfdrop.releases.types import Release, Volumes
from tests.unit.downloads.support import new_desk, release, search_of

COVER = b"RIFF\x00\x00\x00\x00WEBPcover"


def order_of(search_id: str, chosen: Release) -> SendOrder:
    return SendOrder(
        search_id=search_id,
        work_id="mangaupdates:1",
        author="Kentaro Miura",
        series="Berserk",
        choices=(Choice(release_id=chosen.id, volumes=Volumes(kind="single", first=1, last=1)),),
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_the_cover_of_a_download_is_its_picture_kept_by_the_browser_a_while() -> None:
    desk = new_desk()
    desk.covers.covers["mangaupdates:1"] = COVER
    auto = release("Berserk.T01.FRENCH.CBZ")
    desk.finder.searches["s1"] = search_of("s1", [auto])
    [view] = await desk.service.send(order_of("s1", auto), "sylvain")
    await desk.sender.idle()

    response = await read_download_cover(desk.service, view.download.id)

    assert response.status_code == 200
    assert response.body == COVER
    assert response.media_type == "image/webp"
    assert response.headers["cache-control"] == "private, max-age=3600"


@pytest.mark.anyio
async def test_a_download_without_a_cover_or_unknown_is_a_404() -> None:
    desk = new_desk()
    manual = release("Monster.T01.FRENCH.CBZ")
    desk.finder.searches["m1"] = search_of("m1", [manual], mode="manual", title="monster")
    [view] = await desk.service.send(order_of("m1", manual), "sylvain")
    await desk.sender.idle()

    with pytest.raises(ApiError) as none:
        await read_download_cover(desk.service, view.download.id)
    with pytest.raises(ApiError) as unknown:
        await read_download_cover(desk.service, 999)

    assert (none.value.status_code, none.value.code) == (404, "download_cover_not_found")
    assert (unknown.value.status_code, unknown.value.code) == (404, "download_not_found")
