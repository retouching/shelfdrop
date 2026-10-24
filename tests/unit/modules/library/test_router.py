"""shelfdrop.modules.library.router: the name of a file downloaded, the cache of an image, the
errors of a link and of an adoption."""

import pytest

from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode
from shelfdrop.modules.library.router import adopt_files, attachment, link_work, read_image
from shelfdrop.modules.library.schemas import AdoptionBody, AdoptionChoiceBody, WorkLinkBody
from tests.unit.library.test_service import (
    JPEG,
    Works,
    adoption_shelf,
    berserk_work,
    service_of,
    shelf,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_a_file_name_goes_in_ascii_and_whole_in_utf8() -> None:
    assert attachment("Berserk - T01.cbz") == (
        "attachment; filename=\"Berserk - T01.cbz\"; filename*=UTF-8''Berserk%20-%20T01.cbz"
    )
    assert attachment('L\'Été "x"\r\n.epub') == (
        'attachment; filename="L\'_t_ _x___.epub"; '
        "filename*=UTF-8''L%27%C3%89t%C3%A9%20%22x%22%0D%0A.epub"
    )
    assert attachment("") == "attachment; filename=\"file\"; filename*=UTF-8''"


@pytest.mark.anyio
async def test_an_image_with_its_tag_is_kept_for_good_and_a_minute_without() -> None:
    service, _ = service_of(shelf())

    tagged = await read_image("b1", service, width=400, tag="t")
    untagged = await read_image("b1", service, width=400, tag=None)

    assert tagged.body == untagged.body == JPEG
    assert tagged.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert untagged.headers["cache-control"] == "private, max-age=60"


@pytest.mark.anyio
async def test_a_work_unknown_is_a_404() -> None:
    service, _ = service_of(shelf(), Works([berserk_work()]))

    with pytest.raises(ApiError) as raised:
        await link_work("berserk", WorkLinkBody(work_id="kitsu:404"), service)

    assert (raised.value.status_code, raised.value.code) == (404, ErrorCode.WORK_NOT_FOUND)


@pytest.mark.anyio
async def test_an_adoption_refused_is_a_422_naming_its_files() -> None:
    service, _ = service_of(adoption_shelf(), Works([berserk_work()]))
    body = AdoptionBody(items=[AdoptionChoiceBody(item_id="x")], place=True)

    with pytest.raises(ApiError) as raised:
        await adopt_files("berserk", body, service)

    assert (raised.value.status_code, raised.value.code) == (422, ErrorCode.ADOPTION_REFUSED)
    assert raised.value.data == {"reason": "unnumbered", "item_ids": ["x"]}
