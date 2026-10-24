"""shelfdrop.downloads.covers: the cover of the work of an automatic download, read once, kept a
while, joined to an event of each message of a group."""

import dataclasses

import pytest

from shelfdrop.downloads.covers import KEPT_BYTES, KEPT_SECONDS, DownloadCovers
from shelfdrop.downloads.types import Download
from shelfdrop.journal.types import NewEvent
from shelfdrop.releases.types import Volumes
from tests.unit.downloads.support import FakeWorkCovers
from tests.unit.works.support import FixedClock

COVER = b"\x89PNG cover"
BERSERK = Download(
    id=1,
    info_hash=None,
    release_id="0123456789abcdef",
    title="Berserk.T01.FRENCH.CBZ",
    indexer="Nyaa.si",
    size=1000,
    download_url=None,
    work_id="mangaupdates:1",
    work_name="Berserk",
    author="Kentaro Miura",
    series="Berserk",
    volumes=Volumes(kind="single", first=1, last=1),
    kind="manga",
    mode="auto",
    category="manga",
    stage="sent",
    failure=None,
    attempts=1,
    created_at=0,
    created_by="sylvain",
    added_at=0,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def event(event_type: str = "downloaded", group: str = "downloaded:sylvain:0:Berserk") -> NewEvent:
    return NewEvent(type="downloaded" if event_type == "downloaded" else "failed", group=group)


@pytest.mark.anyio
async def test_a_cover_is_read_again_once_it_is_kept_an_hour() -> None:
    source = FakeWorkCovers()
    source.covers["mangaupdates:1"] = COVER
    clock = FixedClock()
    covers = DownloadCovers(source, clock, 30)

    assert await covers.cover(BERSERK) == COVER
    clock.at += KEPT_SECONDS - 1
    assert await covers.cover(BERSERK) == COVER
    clock.at += 1
    assert await covers.cover(BERSERK) == COVER

    assert source.asked == ["mangaupdates:1", "mangaupdates:1"]


@pytest.mark.anyio
async def test_the_covers_kept_never_pass_their_bytes() -> None:
    source = FakeWorkCovers()
    big = b"\xff\xd8\xff" + b"0" * (KEPT_BYTES // 2 - 3)
    for n in range(3):
        source.covers[f"w{n}"] = big
    covers = DownloadCovers(source, FixedClock(), 30)

    for n in range(3):
        await covers.cover(dataclasses.replace(BERSERK, work_id=f"w{n}"))

    assert list(covers.covers) == ["w1", "w2"]


@pytest.mark.anyio
async def test_only_a_send_and_an_end_of_an_automatic_download_take_the_cover() -> None:
    source = FakeWorkCovers()
    source.covers["mangaupdates:1"] = COVER
    covers = DownloadCovers(source, FixedClock(), 30)
    manual = dataclasses.replace(BERSERK, mode="manual", work_id=None)

    failed = await covers.dress(BERSERK, event("failed"))
    by_hand = await covers.dress(manual, event(group="downloaded:other"))
    dressed = await covers.dress(BERSERK, event())

    assert (failed.cover, by_hand.cover, dressed.cover) == (None, None, COVER)


@pytest.mark.anyio
async def test_a_work_without_a_cover_lets_the_next_event_of_its_group_ask_again() -> None:
    source = FakeWorkCovers()
    clock = FixedClock()
    covers = DownloadCovers(source, clock, 30)

    assert (await covers.dress(BERSERK, event())).cover is None
    source.covers["mangaupdates:1"] = COVER
    clock.at += KEPT_SECONDS

    assert (await covers.dress(BERSERK, event())).cover == COVER
