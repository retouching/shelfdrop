import os
from datetime import datetime
from pathlib import Path

import pytest

from shelfdrop.placement.byhand import scan_slot
from shelfdrop.placement.paths import SEPARATOR
from shelfdrop.placement.types import (
    ChaptersRequest,
    IgnoreRequest,
    VolumeRange,
    VolumeRequest,
)
from shelfdrop.releases.types import Volumes
from tests.unit.placement.support import Bench, cbz, completed, new_bench


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def chapters_download(bench: Bench, tmp_path: Path) -> tuple[int, list[Path]]:
    torrent = tmp_path / "torrents" / "Chainsaw Man"
    files = [
        cbz(torrent / f"Chainsaw Man - Ch. {n}.cbz", [f"{n}.jpg"]) for n in ("206", "207", "230")
    ]
    download = completed(bench, torrent, series="Chainsaw Man", volumes=Volumes(kind="unknown"))
    return download.id, files


@pytest.mark.anyio
async def test_a_release_left_to_ranger_is_listed_then_merged_into_its_volumes(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path)
    download_id, files = chapters_download(bench, tmp_path)
    await bench.service.round()
    await bench.hand.round()
    await bench.hand.round()

    [item] = bench.shelf.items.values()
    assert (item.state, item.download_id, item.chapters) == (
        "chapters",
        download_id,
        (206, 207, 230),
    )
    asked = ChaptersRequest(
        work_id="mangaupdates:1",
        series="Chainsaw Man",
        author="Tatsuki Fujimoto",
        volumes=(VolumeRange(volume=23, first=206, last=207),),
        rest="keep",
    )
    assert bench.shelf.ask(item.id, asked, 0)
    await bench.hand.round()

    kept = bench.shelf.items[item.id]
    assert (kept.state, kept.request, kept.files) == ("chapters", None, (str(files[2]),))
    assert kept.chapters == (230.0,)
    assert (bench.roots["manga"] / "Chainsaw Man" / "Chainsaw Man - T23.cbz").is_file()
    assert all(f.exists() for f in files)
    assert bench.downloads.rows[download_id].stage == "unplaced"
    [placed] = bench.journal.of("placed")
    assert placed.facts["destination"] == f"BD & Mangas{SEPARATOR}Chainsaw Man"

    rest = ChaptersRequest(work_id=None, series="Chainsaw Man", author="", volumes=(), rest="place")
    assert bench.shelf.ask(item.id, rest, 0)
    await bench.hand.round()

    assert bench.shelf.items[item.id].state == "placed"
    assert bench.downloads.rows[download_id].stage == "placed"


@pytest.mark.anyio
async def test_a_file_of_the_library_is_moved_and_a_name_taken_refuses(tmp_path: Path) -> None:
    bench = new_bench(tmp_path)
    loose = bench.roots["ebook"] / "Goggins.epub"
    loose.write_bytes(b"book")
    await bench.hand.round()
    [item] = bench.shelf.items.values()
    assert (item.state, item.reason, item.origin) == ("misplaced", "root", "library")

    asked = VolumeRequest(
        kind="ebook", work_id=None, series="Never Finished", author="David Goggins", volume=1
    )
    assert bench.shelf.ask(item.id, asked, 0)
    await bench.hand.round()

    target = (
        bench.roots["ebook"]
        / "David Goggins"
        / "Never Finished"
        / "01 - Never Finished"
        / "Never Finished - T01 - Never Finished.epub"
    )
    assert target.read_bytes() == b"book"
    assert not loose.exists()
    assert bench.shelf.items[item.id].state == "placed"

    again = bench.roots["ebook"] / "copy.epub"
    again.write_bytes(b"other")
    bench.clock.at += 24 * 3600
    await bench.hand.round()
    [other] = [i for i in bench.shelf.items.values() if i.state != "placed"]
    assert bench.shelf.ask(other.id, asked, 0)
    await bench.hand.round()
    assert bench.shelf.items[other.id].error == "exists"
    assert again.exists()


@pytest.mark.anyio
async def test_the_scan_runs_once_a_day_and_when_the_page_asks(tmp_path: Path) -> None:
    bench = new_bench(tmp_path)
    await bench.hand.round()
    await bench.hand.round()
    assert len(bench.shelf.scans) == 1

    (bench.roots["manga"] / "Berserk T01.cbz").write_bytes(b"x")
    bench.shelf.add_task("scan", "", b"", 0)
    await bench.hand.round()

    [item] = bench.shelf.items.values()
    assert item.reason == "root"
    [message] = bench.journal.of("misplaced")
    assert message.facts == {"library": "BD & Mangas", "count": 1}
    os.remove(bench.roots["manga"] / "Berserk T01.cbz")
    bench.shelf.add_task("scan", "", b"", 0)
    await bench.hand.round()
    assert bench.shelf.items == {}


@pytest.mark.anyio
async def test_the_rest_of_a_download_placed_in_part_is_listed_alone_then_ignored(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path)
    torrent = tmp_path / "torrents" / "Berserk"
    files = [cbz(torrent / n, ["1.jpg"]) for n in ("Berserk T41.cbz", "Berserk bonus.cbz")]
    download = completed(bench, torrent, volumes=Volumes(kind="unknown"))
    await bench.service.round()
    await bench.hand.round()

    # The volume placed is not listed again: only the book without a volume.
    [item] = bench.shelf.items.values()
    assert (item.path, item.state, item.reason) == (str(files[1]), "unlinked", "no_volume")
    assert bench.shelf.ask(item.id, IgnoreRequest(), 0)
    await bench.hand.round()

    assert bench.shelf.items[item.id].state == "ignored"
    assert bench.shelf.count_open() == 0
    assert all(f.is_file() for f in files)
    assert sorted(p.name for p in (bench.roots["manga"] / "Berserk").iterdir()) == [
        "Berserk - T41.cbz",
        "cover.jpg",
    ]
    row = bench.downloads.rows[download.id]
    assert (row.stage, row.destination) == ("placed", f"BD & Mangas{SEPARATOR}Berserk")
    assert bench.qui.torrents[row.info_hash or ""]["tags"] == "placé"
    assert bench.journal.of("placed") == []


@pytest.mark.anyio
async def test_a_file_of_the_library_ignored_stays_ignored_at_the_next_scan(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path)
    loose = bench.roots["ebook"] / "Goggins.epub"
    loose.write_bytes(b"book")
    await bench.hand.round()
    [item] = bench.shelf.items.values()
    assert bench.shelf.ask(item.id, IgnoreRequest(), 0)
    await bench.hand.round()

    bench.shelf.add_task("scan", "", b"", 0)
    await bench.hand.round()

    assert list(bench.shelf.items) == [item.id]
    assert bench.shelf.items[item.id].state == "ignored"
    assert loose.read_bytes() == b"book"
    loose.unlink()
    bench.shelf.add_task("scan", "", b"", 0)
    await bench.hand.round()
    assert bench.shelf.items == {}


def test_the_slot_of_the_scan_is_the_last_one_passed() -> None:
    now = datetime(2026, 10, 21, 3, 0).astimezone().timestamp()

    assert scan_slot(now, 4, 30) == datetime(2026, 10, 20, 4, 30).astimezone().timestamp()
    assert scan_slot(now, 2, 0) == datetime(2026, 10, 21, 2, 0).astimezone().timestamp()


@pytest.mark.anyio
async def test_a_release_in_chapters_counts_the_chapters_loose_on_the_shelf_as_they_come(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path)
    folder = bench.roots["manga"] / "Chainsaw Man"
    cbz(folder / "Chainsaw Man - T22.cbz", ["1.jpg"])
    cbz(folder / "Chainsaw Man - T23 - Ch. 208.cbz", ["208.jpg"])
    download_id, _ = chapters_download(bench, tmp_path)
    await bench.service.round()
    await bench.hand.round()

    [item] = [i for i in bench.shelf.items.values() if i.download_id == download_id]
    assert (item.existing, item.loose) == ((22,), (208.0,))
    cbz(folder / "Chainsaw Man - Ch. 209.cbz", ["209.jpg"])
    await bench.hand.round()

    assert bench.shelf.items[item.id].loose == (208.0, 209.0)
    asked = ChaptersRequest(
        work_id=None,
        series="Chainsaw Man",
        author="",
        volumes=(VolumeRange(volume=23, first=206, last=209),),
        rest="keep",
    )
    assert bench.shelf.ask(item.id, asked, 0)
    await bench.hand.round()
    assert (folder / "Chainsaw Man - T23.cbz").is_file()
    assert not (folder / "Chainsaw Man - Ch. 209.cbz").exists()


@pytest.mark.anyio
async def test_a_file_sent_is_taken_into_ranger_placed_from_there_and_one_left_goes(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path)
    sent = bench.uploads.add("Berserk T41.cbz", 3, 10, 0)
    bench.store.write_chunk(sent.id, 0, b"abc")
    bench.store.put_together(sent.id, sent.name, 1)
    bench.uploads.mark(sent.id, "verified", 0)
    old = bench.uploads.add("Old.epub", 3, 10, 0)
    bench.store.write_chunk(old.id, 0, b"abc")
    await bench.hand.round()

    [item] = [i for i in bench.shelf.items.values() if i.origin == "upload"]
    envois = tmp_path / "files" / "envois"
    assert (item.name, item.kind, item.path) == (
        "Berserk T41.cbz",
        "manga",
        str(envois / str(sent.id) / "Berserk T41.cbz"),
    )
    assert bench.uploads.rows[sent.id].state == "listed"
    assert not bench.store.folder(sent.id).exists()
    asked = VolumeRequest(
        kind="manga", work_id=None, series="Berserk", author="Kentaro Miura", volume=41
    )
    assert bench.shelf.ask(item.id, asked, 0)
    await bench.hand.round()

    assert (bench.roots["manga"] / "Berserk" / "Berserk - T41.cbz").read_bytes() == b"abc"
    assert bench.shelf.items[item.id].state == "placed"
    assert not envois.exists() or list(envois.iterdir()) == []

    left = bench.uploads.add("Left.epub", 3, 10, 0)
    bench.store.write_chunk(left.id, 0, b"abc")
    bench.store.put_together(left.id, left.name, 1)
    bench.uploads.mark(left.id, "verified", 0)
    await bench.hand.round()
    [kept] = [i for i in bench.shelf.items.values() if i.name == "Left.epub"]
    bench.clock.at += 8 * 24 * 3600
    await bench.hand.round()

    assert kept.id not in bench.shelf.items
    assert kept.path == str(envois / str(left.id) / "Left.epub")
    assert not (envois / str(left.id)).exists()
    assert old.id not in bench.uploads.rows
    assert not bench.store.folder(old.id).exists()


@pytest.mark.anyio
async def test_a_download_copied_in_part_lists_its_rest_alone_then_copies_it(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path, mode="copy")
    torrent = tmp_path / "torrents" / "Berserk"
    files = [cbz(torrent / n, ["1.jpg"]) for n in ("Berserk T41.cbz", "Berserk bonus.cbz")]
    download = completed(bench, torrent, volumes=Volumes(kind="unknown"))
    await bench.service.round()
    await bench.hand.round()

    # The copy shares no inode with its source: it is known by the source it names.
    [item] = bench.shelf.items.values()
    assert item.path == str(files[1])
    assert bench.downloads.rows[download.id].copied is True
    asked = VolumeRequest(
        kind="manga", work_id=None, series="Berserk", author="Kentaro Miura", volume=42
    )
    assert bench.shelf.ask(item.id, asked, 0)
    await bench.hand.round()

    placed = bench.shelf.items[item.id]
    assert (placed.state, placed.copied) == ("placed", True)
    target = bench.roots["manga"] / "Berserk" / "Berserk - T42.cbz"
    assert target.stat().st_ino != files[1].stat().st_ino
    assert files[1].is_file()
    assert bench.downloads.rows[download.id].stage == "placed"
    [event] = bench.journal.of("placed")
    assert event.facts["copied"] is True


@pytest.mark.anyio
async def test_a_file_of_the_library_is_moved_whatever_the_mode(tmp_path: Path) -> None:
    bench = new_bench(tmp_path, mode="copy")
    loose = bench.roots["manga"] / "Berserk T03.cbz"
    cbz(loose, ["1.jpg"])
    inode = loose.stat().st_ino
    await bench.hand.round()
    [item] = bench.shelf.items.values()

    asked = VolumeRequest(
        kind="manga", work_id=None, series="Berserk", author="Kentaro Miura", volume=3
    )
    assert bench.shelf.ask(item.id, asked, 0)
    await bench.hand.round()

    target = bench.roots["manga"] / "Berserk" / "Berserk - T03.cbz"
    # Moved: linked then its old name removed, no second copy.
    assert target.stat().st_ino == inode
    assert not loose.exists()
    assert bench.shelf.items[item.id].copied is False
    assert [f.copied_from for f in bench.shelf.files] == [None]
