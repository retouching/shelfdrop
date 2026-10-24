"""DownloadService: the releases of a search sent with what they are for, the automatic rules,
the downloads as qBittorrent has them, a send tried again (plan section 3, points 1 to 3 and 10,
points 12 and 13 for the automatic downloads)."""

import dataclasses

import pytest

from shelfdrop.downloads.exceptions import (
    DownloadNotFoundError,
    NotAutomaticError,
    NotRetryableError,
    UnknownReleasesError,
)
from shelfdrop.downloads.types import Choice, SendOrder
from shelfdrop.releases.exceptions import SearchNotFoundError
from shelfdrop.releases.types import Release, Torrent, Volumes
from shelfdrop.utils.torrent import torrent_id
from tests.unit.clients.support import FakeQui
from tests.unit.downloads.support import Desk, new_desk, release, search_of
from tests.unit.support import torrent_file

T01_T11 = Volumes(kind="range", first=1, last=11)
COVER = b"\x89PNG cover"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def order_of(search_id: str, *releases: Release, volumes: Volumes = T01_T11) -> SendOrder:
    return SendOrder(
        search_id=search_id,
        work_id="mangaupdates:1",
        author="Kentaro Miura",
        series="Berserk",
        choices=tuple(Choice(release_id=r.id, volumes=volumes) for r in releases),
    )


def with_torrents(desk: Desk, *releases: Release) -> None:
    for r in releases:
        assert r.download_url is not None
        desk.prowlarr.torrents[r.download_url] = Torrent(file=torrent_file(r.title))


@pytest.mark.anyio
async def test_a_work_is_sent_with_its_author_its_series_its_volumes_and_who_asked() -> None:
    desk = new_desk()
    pack, single = release("Berserk.T01-T11.FRENCH.CBZ"), release("Berserk.T12.FRENCH.CBZ")
    desk.finder.searches["s1"] = search_of("s1", [pack, single], title="Berserk")
    with_torrents(desk, pack, single)

    views = await desk.service.send(order_of("s1", pack, single, pack), "sylvain")
    await desk.sender.idle()

    # Once each, waiting while they are sent.
    assert [v.progress.state for v in views] == ["waiting", "waiting"]
    sent = [desk.repository.rows[v.download.id] for v in views]
    assert [(d.title, d.stage) for d in sent] == [
        ("Berserk.T01-T11.FRENCH.CBZ", "sent"),
        ("Berserk.T12.FRENCH.CBZ", "sent"),
    ]
    first = sent[0]
    assert (first.mode, first.kind, first.category) == ("auto", "manga", "manga")
    assert (first.work_id, first.work_name, first.author, first.series) == (
        "mangaupdates:1",
        "Berserk",
        "Kentaro Miura",
        "Berserk",
    )
    assert first.volumes == T01_T11
    assert (first.created_by, first.attempts) == ("sylvain", 1)
    assert desk.repository.commits >= 1


@pytest.mark.anyio
async def test_an_automatic_download_never_takes_a_release_it_may_not() -> None:
    desk = new_desk()
    allowed = release("Berserk.T01.FRENCH.CBZ")
    c411 = release("Berserk.T02.FRENCH.CBZ", indexer="C411", automatic=False)
    desk.finder.searches["s1"] = search_of("s1", [allowed, c411])

    with pytest.raises(NotAutomaticError) as refused:
        await desk.service.send(order_of("s1", allowed, c411), "sylvain")

    assert refused.value.ids == [c411.id]
    assert desk.repository.rows == {}


@pytest.mark.anyio
async def test_a_manual_search_gives_manual_downloads_into_their_category() -> None:
    desk = new_desk()
    c411 = release("Berserk.Deluxe.T01.CBZ", indexer="C411", automatic=False)
    desk.finder.searches["m1"] = search_of(
        "m1", [c411], mode="manual", kind="ebook", title="berserk deluxe"
    )
    with_torrents(desk, c411)

    views = await desk.service.send(order_of("m1", c411), "sylvain")
    await desk.sender.idle()

    download = desk.repository.rows[views[0].download.id]
    assert (download.mode, download.category, download.stage) == (
        "manual",
        "shelfdrop-manual",
        "sent",
    )
    # No work, no author, no series: placed by hand.
    assert (download.work_id, download.work_name, download.author, download.series) == (
        None,
        "berserk deluxe",
        "",
        "",
    )


@pytest.mark.anyio
async def test_a_release_or_a_search_unknown_sends_nothing() -> None:
    desk = new_desk()
    kept = release("Berserk.T01.FRENCH.CBZ")
    # Prowlarr gave no download link for it.
    no_link = dataclasses.replace(release("Berserk.T02.FRENCH.CBZ"), download_url=None)
    desk.finder.searches["s1"] = search_of("s1", [kept, no_link])

    with pytest.raises(UnknownReleasesError) as unknown:
        await desk.service.send(
            order_of("s1", kept, no_link, release("Berserk.T03.FRENCH.CBZ")), "sylvain"
        )
    with pytest.raises(SearchNotFoundError):
        await desk.service.send(order_of("gone", kept), "sylvain")

    assert len(unknown.value.ids) == 2
    assert desk.repository.rows == {}


@pytest.mark.anyio
async def test_the_downloads_show_the_figures_of_qbittorrent_and_complete_once() -> None:
    qui = FakeQui(added_as={"state": "downloading", "progress": 0.42, "dlspeed": 4096, "eta": 120})
    desk = new_desk(qui=qui)
    desk.covers.covers["mangaupdates:1"] = COVER
    auto = release("Berserk.T01.FRENCH.CBZ")
    manual = release("Monster.T01.FRENCH.CBZ")
    desk.finder.searches["s1"] = search_of("s1", [auto])
    desk.finder.searches["m1"] = search_of("m1", [manual], mode="manual", title="monster")
    with_torrents(desk, auto, manual)
    await desk.service.send(order_of("s1", auto), "sylvain")
    desk.clock.at += 1
    await desk.service.send(order_of("m1", manual), "sylvain")
    await desk.sender.idle()

    views = await desk.service.read()

    # The newest first.
    assert [(v.download.title, v.progress.state) for v in views] == [
        ("Monster.T01.FRENCH.CBZ", "downloading"),
        ("Berserk.T01.FRENCH.CBZ", "downloading"),
    ]
    assert (views[1].progress.percent, views[1].progress.speed, views[1].progress.eta) == (
        42,
        4096,
        120,
    )
    for torrent in qui.torrents.values():
        torrent.update(state="stalledUP", progress=1.0)
    done = await desk.service.read()
    assert [v.progress.state for v in done] == ["to_place", "placing"]
    assert {d.stage for d in desk.repository.rows.values()} == {"completed"}
    # Each end once in the journal: downloaded for the automatic one, to place for the manual.
    assert [(e.type, e.facts.get("reason")) for e in desk.journal.events[2:]] == [
        ("to_place", "manual"),
        ("downloaded", None),
    ]
    # The cover of the work goes with the events of the automatic download alone, read once.
    assert [(e.type, e.cover) for e in desk.journal.events] == [
        ("sent", COVER),
        ("sent", None),
        ("to_place", None),
        ("downloaded", COVER),
    ]
    assert desk.covers.asked == ["mangaupdates:1"]
    # Completed: qBittorrent is not asked again.
    asked = len(qui.requests)
    qui.torrents.clear()
    assert [v.progress.state for v in await desk.service.read()] == ["to_place", "placing"]
    assert len(qui.requests) == asked


@pytest.mark.anyio
async def test_qbittorrent_down_leaves_the_downloads_sent_waiting() -> None:
    desk = new_desk()
    auto = release("Berserk.T01.FRENCH.CBZ")
    desk.finder.searches["s1"] = search_of("s1", [auto])
    with_torrents(desk, auto)
    await desk.service.send(order_of("s1", auto), "sylvain")
    await desk.sender.idle()
    desk.qui.down = True

    views = await desk.service.read()

    assert [v.progress.state for v in views] == ["waiting"]
    assert desk.repository.rows[views[0].download.id].stage == "sent"


@pytest.mark.anyio
async def test_a_torrent_not_received_is_sent_again_and_a_duplicate_never_is() -> None:
    desk = new_desk(qui=FakeQui(lost=1))
    lost = release("Berserk.T01.FRENCH.CBZ")
    desk.finder.searches["s1"] = search_of("s1", [lost])
    with_torrents(desk, lost)
    views = await desk.service.send(order_of("s1", lost), "sylvain")
    await desk.sender.idle()
    download_id = views[0].download.id
    assert (await desk.service.read())[0].progress.reason == "not_received"

    again = await desk.service.retry(download_id)
    await desk.sender.idle()

    assert again.progress.state == "waiting"
    assert again.download.attempts == 2
    retried = desk.repository.rows[download_id]
    assert (retried.stage, retried.attempts, retried.category) == ("sent", 2, "manga")
    with pytest.raises(NotRetryableError):
        await desk.service.retry(download_id)
    with pytest.raises(DownloadNotFoundError):
        await desk.service.retry(99)

    twice = release("Berserk.T02.FRENCH.CBZ")
    data = torrent_file(twice.title)
    digest = torrent_id(data)
    assert digest is not None
    desk.qui.torrents[digest] = {"hash": digest, "state": "uploading"}
    desk.finder.searches["s2"] = search_of("s2", [twice])
    assert twice.download_url is not None
    desk.prowlarr.torrents[twice.download_url] = Torrent(file=data)
    duplicate = (await desk.service.send(order_of("s2", twice), "sylvain"))[0].download.id
    await desk.sender.idle()
    with pytest.raises(NotRetryableError):
        await desk.service.retry(duplicate)


@pytest.mark.anyio
async def test_the_cover_of_a_download_is_the_one_of_its_work_and_its_type() -> None:
    desk = new_desk()
    desk.covers.covers["mangaupdates:1"] = COVER
    auto = release("Berserk.T01.FRENCH.CBZ")
    manual = release("Monster.T01.FRENCH.CBZ")
    desk.finder.searches["s1"] = search_of("s1", [auto])
    desk.finder.searches["m1"] = search_of("m1", [manual], mode="manual", title="monster")
    [sent] = await desk.service.send(order_of("s1", auto), "sylvain")
    [by_hand] = await desk.service.send(order_of("m1", manual), "sylvain")
    await desk.sender.idle()

    assert await desk.service.cover(sent.download.id) == (COVER, "image/png")
    # A manual download has no work: no cover, and the sources are not asked.
    assert await desk.service.cover(by_hand.download.id) is None
    with pytest.raises(DownloadNotFoundError):
        await desk.service.cover(999)
    assert desk.covers.asked == ["mangaupdates:1"]
