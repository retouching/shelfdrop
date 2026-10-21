"""shelfdrop.downloads.sender: the torrent fetched through Prowlarr, its id, the send to
qBittorrent looked for by its hash 3 times, the duplicates (plan section 3, point 2)."""

import time

import pytest

from shelfdrop.downloads.types import DownloadOptions, NewDownload
from shelfdrop.releases.types import Torrent, Volumes
from shelfdrop.utils.torrent import torrent_id
from tests.unit.clients.support import FakeQui
from tests.unit.downloads.support import Desk, new_desk
from tests.unit.support import torrent_file

LINK = "http://prowlarr.test/1/download?link=berserk"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def order(desk: Desk, *, link: str = LINK, mode: str = "auto") -> int:
    """A download waiting to be sent, as the service writes it."""
    download = desk.repository.add(
        NewDownload(
            release_id="0123456789abcdef",
            guid="g",
            title="Berserk.T01.FRENCH.CBZ",
            indexer_id=1,
            indexer="Nyaa.si",
            size=1000,
            download_url=link,
            work_id="mangaupdates:1",
            work_name="Berserk",
            author="Kentaro Miura",
            series="Berserk",
            volumes=Volumes(kind="single", first=1, last=1),
            kind="manga",
            mode="auto" if mode == "auto" else "manual",
            category="manga" if mode == "auto" else "shelfdrop-manual",
            created_at=0,
            created_by="sylvain",
        )
    )
    return download.id


def infos(qui: FakeQui) -> int:
    """The looks for a torrent qBittorrent received."""
    return sum(1 for r in qui.requests if r.url.path.endswith("/torrents/info"))


async def send(desk: Desk, download_id: int) -> None:
    desk.sender.start([download_id])
    await desk.sender.idle()


@pytest.mark.anyio
async def test_the_torrent_is_added_into_its_category_and_found_by_its_hash() -> None:
    desk = new_desk()
    data = torrent_file("Berserk T01.cbz")
    desk.prowlarr.torrents[LINK] = Torrent(file=data)
    download_id = order(desk)

    await send(desk, download_id)

    download = desk.repository.rows[download_id]
    assert download.stage == "sent"
    assert download.info_hash == torrent_id(data)
    assert download.added_at is not None
    assert desk.qui.added == [{"category": b"manga", "torrents": data}]
    # Looked for once before the add (a duplicate?), once after.
    assert infos(desk.qui) == 2
    assert desk.repository.torrents[download_id] == Torrent(file=data)


@pytest.mark.anyio
async def test_a_torrent_qbittorrent_loses_is_looked_for_3_times_then_not_received() -> None:
    desk = new_desk(qui=FakeQui(lost=1))
    desk.prowlarr.torrents[LINK] = Torrent(file=torrent_file("Berserk T01.cbz"))
    download_id = order(desk)

    await send(desk, download_id)

    download = desk.repository.rows[download_id]
    assert (download.stage, download.failure) == ("failed", "not_received")
    assert infos(desk.qui) == 1 + 3


@pytest.mark.anyio
async def test_the_looks_are_spaced_by_the_delay_of_the_options() -> None:
    desk = new_desk(qui=FakeQui(lost=1), options=DownloadOptions(check_seconds=0.05))
    desk.prowlarr.torrents[LINK] = Torrent(file=torrent_file("Berserk T01.cbz"))
    download_id = order(desk)

    begin = time.monotonic()
    await send(desk, download_id)

    # 3 looks, 2 delays between them.
    assert time.monotonic() - begin >= 0.1


@pytest.mark.anyio
async def test_a_torrent_already_in_qbittorrent_is_a_duplicate_never_added() -> None:
    data = torrent_file("Berserk T01.cbz")
    digest = torrent_id(data)
    assert digest is not None
    desk = new_desk(qui=FakeQui(torrents={digest: {"hash": digest, "state": "uploading"}}))
    desk.prowlarr.torrents[LINK] = Torrent(file=data)
    download_id = order(desk)

    await send(desk, download_id)

    download = desk.repository.rows[download_id]
    assert (download.stage, download.failure) == ("failed", "duplicate")
    assert desk.qui.added == []


@pytest.mark.anyio
async def test_a_magnet_link_is_sent_as_a_link() -> None:
    magnet = "magnet:?xt=urn:btih:" + "d" * 40
    desk = new_desk()
    desk.prowlarr.torrents[LINK] = Torrent(magnet=magnet)
    download_id = order(desk, mode="manual")

    await send(desk, download_id)

    assert desk.repository.rows[download_id].stage == "sent"
    assert desk.repository.rows[download_id].info_hash == "d" * 40
    assert desk.qui.added == [{"category": b"shelfdrop-manual", "urls": magnet.encode()}]


@pytest.mark.anyio
@pytest.mark.parametrize("answer", [None, Torrent(file=b"<html>410</html>")])
async def test_no_torrent_from_prowlarr_is_not_received(answer: Torrent | None) -> None:
    desk = new_desk()
    if answer is not None:
        desk.prowlarr.torrents[LINK] = answer
    download_id = order(desk)

    await send(desk, download_id)

    download = desk.repository.rows[download_id]
    assert (download.stage, download.failure) == ("failed", "not_received")
    assert desk.qui.requests == []


@pytest.mark.anyio
async def test_qbittorrent_down_or_refusing_is_not_received() -> None:
    desk = new_desk(qui=FakeQui(down=True))
    desk.prowlarr.torrents[LINK] = Torrent(file=torrent_file("Berserk T01.cbz"))
    first = order(desk)
    await send(desk, first)
    desk.qui.down, desk.qui.refuse = False, True
    second = order(desk)
    await send(desk, second)

    assert [desk.repository.rows[i].failure for i in (first, second)] == [
        "not_received",
        "not_received",
    ]


@pytest.mark.anyio
async def test_a_send_again_takes_the_same_torrent_and_finds_one_added_before() -> None:
    desk = new_desk(qui=FakeQui(lost=1))
    data = torrent_file("Berserk T01.cbz")
    desk.prowlarr.torrents[LINK] = Torrent(file=data)
    download_id = order(desk)
    await send(desk, download_id)
    # Prowlarr gives nothing any more: the torrent read the first time is sent again.
    desk.prowlarr.torrents.clear()
    desk.repository.mark_retried(download_id)

    await send(desk, download_id)

    download = desk.repository.rows[download_id]
    assert (download.stage, download.attempts) == ("sent", 2)
    assert [a["torrents"] for a in desk.qui.added] == [data, data]
    assert desk.prowlarr.asked == [LINK]

    # A first add lost, found later: a send again finds it, it is no duplicate.
    late = new_desk(qui=FakeQui(lost=1))
    late.prowlarr.torrents[LINK] = Torrent(file=data)
    other = order(late)
    await send(late, other)
    digest = late.repository.rows[other].info_hash
    assert digest is not None
    late.qui.torrents[digest] = {"hash": digest, "state": "downloading"}
    late.repository.mark_retried(other)
    await send(late, other)
    assert late.repository.rows[other].stage == "sent"
    assert len(late.qui.added) == 1


@pytest.mark.anyio
async def test_the_sends_a_stop_left_are_resumed_and_one_runs_once() -> None:
    desk = new_desk()
    desk.prowlarr.torrents[LINK] = Torrent(file=torrent_file("Berserk T01.cbz"))
    download_id = order(desk)

    await desk.sender.resume()
    desk.sender.start([download_id])
    await desk.sender.idle()

    assert desk.repository.rows[download_id].stage == "sent"
    assert len(desk.qui.added) == 1


@pytest.mark.anyio
async def test_the_journal_gets_a_send_a_failure_and_a_retry_but_no_duplicate() -> None:
    desk = new_desk()
    data = torrent_file("Berserk T01.cbz")
    desk.prowlarr.torrents[LINK] = Torrent(file=data)
    sent = order(desk)
    lost = order(desk, link="http://prowlarr.test/1/download?link=gone")

    await send(desk, sent)
    await send(desk, lost)
    duplicate = order(desk)
    await send(desk, duplicate)
    desk.prowlarr.torrents["http://prowlarr.test/1/download?link=gone"] = Torrent(
        file=torrent_file("Berserk T02.cbz")
    )
    desk.repository.mark_retried(lost)
    await send(desk, lost)

    assert [e.type for e in desk.journal.events] == ["sent", "failed", "retry"]
    first, failed, retry = desk.journal.events
    assert first.facts == {
        "work": "Berserk",
        "volumes": [1],
        "tracker": "Nyaa.si",
        "size": 1000,
        "mode": "auto",
        "actor": "sylvain",
    }
    assert failed.facts == {"what": "not_received", "release": "Berserk.T01.FRENCH.CBZ"}
    assert retry.facts["attempt"] == 2
    assert retry.facts["result"] == "sent"
    # The downloads of one request share the group of their message.
    assert first.group == "sent:sylvain:0:Berserk"
