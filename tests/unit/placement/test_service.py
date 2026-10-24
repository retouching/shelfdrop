"""shelfdrop.placement.service: the automatic downloads complete put on the shelf, the journal,
qBittorrent and Jellyfin told, the metadata locked, the covers asked for written."""

from pathlib import Path

import pytest

from shelfdrop.placement.types import AdoptOrder, PlacedFile
from shelfdrop.releases.types import Volumes
from tests.unit.placement.support import (
    JPEG,
    Bench,
    FakeCovers,
    FakeTools,
    cbz,
    completed,
    new_bench,
)

SEPARATOR = " \u203a "


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def berserk(bench: Bench, tmp_path: Path) -> Path:
    torrent = tmp_path / "torrents" / "manga" / "Berserk T41-T42"
    for n in (41, 42):
        cbz(torrent / f"Berserk.T{n}.FRENCH.CBZ.cbz", [f"{n}.jpg"])
    return torrent


@pytest.mark.anyio
async def test_a_download_complete_is_placed_tagged_scanned_and_journaled(tmp_path: Path) -> None:
    bench = new_bench(tmp_path)
    download = completed(bench, berserk(bench, tmp_path))

    await bench.service.round()

    row = bench.downloads.rows[download.id]
    assert row.stage == "placed"
    assert row.destination == f"BD & Mangas{SEPARATOR}Berserk"
    series = bench.roots["manga"] / "Berserk"
    assert sorted(p.name for p in series.iterdir()) == [
        "Berserk - T41.cbz",
        "Berserk - T42.cbz",
        "cover.jpg",
    ]
    assert [(f.volume, f.series, f.work_id) for f in bench.shelf.files] == [
        (41, "Berserk", "mangaupdates:1"),
        (42, "Berserk", "mangaupdates:1"),
    ]
    assert bench.qui.torrents[row.info_hash or ""]["tags"] == "placé"
    assert bench.jellyfin.refreshed[0][0] == "lib-manga"
    [placed] = bench.journal.of("placed")
    assert placed.facts == {
        "destination": f"BD & Mangas{SEPARATOR}Berserk",
        "volumes": [41, 42],
        "skipped": [],
    }
    assert placed.cover == JPEG + b"41.jpg"


@pytest.mark.anyio
async def test_a_download_sent_is_completed_by_the_worker_too_once(tmp_path: Path) -> None:
    bench = new_bench(tmp_path, covers=FakeCovers({"mangaupdates:1": JPEG + b"work"}))
    download = completed(bench, berserk(bench, tmp_path))
    bench.downloads.change(download.id, stage="sent")

    await bench.service.round()
    await bench.service.round()

    assert bench.downloads.rows[download.id].stage == "placed"
    assert [e.type for e in bench.journal.events] == ["downloaded", "placed"]
    # The end of an automatic download shows the cover of its work.
    assert bench.journal.events[0].cover == JPEG + b"work"


@pytest.mark.anyio
async def test_a_release_in_chapters_goes_to_ranger(tmp_path: Path) -> None:
    bench = new_bench(tmp_path)
    torrent = tmp_path / "torrents" / "Chainsaw Man"
    for chapter in ("230", "231", "231.5", "233"):
        cbz(torrent / f"Chainsaw Man - Ch. {chapter}.cbz", ["1.jpg"])
    download = completed(bench, torrent, series="Chainsaw Man", volumes=Volumes(kind="unknown"))

    await bench.service.round()

    row = bench.downloads.rows[download.id]
    assert (row.stage, row.unplaced) == ("unplaced", "chapters")
    assert not (bench.roots["manga"] / "Chainsaw Man").exists()
    [left] = bench.journal.of("to_place")
    assert left.facts["reason"] == "chapters"
    assert bench.journal.of("failed") == []
    assert "tags" not in bench.qui.torrents[row.info_hash or ""]


def audiobook(bench: Bench, tmp_path: Path, *, picture: bool = False) -> int:
    torrent = tmp_path / "torrents" / "audiobook" / "Ne.Cede.Jamais.David.Goggins"
    torrent.mkdir(parents=True)
    for n in (1, 2, 3):
        (torrent / f"Ne cede jamais - {n:03d}.mp3").write_bytes(b"[%d]" % n)
    if picture:
        (torrent / "cover.jpg").write_bytes(JPEG + b"torrent")
    download = completed(
        bench,
        torrent,
        kind="audiobook",
        series="Ne cède jamais",
        author="David Goggins",
        title="Ne.Cede.Jamais.David.Goggins.FRENCH.MP3",
        volumes=Volumes(kind="single", first=1, last=1),
        work_id="openlibrary:OL1W",
    )
    return download.id


@pytest.mark.anyio
async def test_a_download_with_a_book_without_a_volume_is_placed_in_part(tmp_path: Path) -> None:
    bench = new_bench(tmp_path)
    torrent = berserk(bench, tmp_path)
    cbz(torrent / "Berserk bonus.cbz", ["b.jpg"])
    download = completed(bench, torrent)

    await bench.service.round()

    row = bench.downloads.rows[download.id]
    assert (row.stage, row.unplaced) == ("unplaced", "no_volume")
    assert [f.volume for f in bench.shelf.files] == [41, 42]
    assert (bench.roots["manga"] / "Berserk" / "Berserk - T42.cbz").is_file()
    # Placed in part: the event to place alone, no tag until Ranger ends it.
    [left] = bench.journal.of("to_place")
    assert left.facts["reason"] == "no_volume"
    assert bench.journal.of("placed") == []
    assert "tags" not in bench.qui.torrents[row.info_hash or ""]
    assert bench.jellyfin.refreshed[0][0] == "lib-manga"


@pytest.mark.anyio
async def test_the_tracks_merge_into_one_m4b_with_the_cover_of_the_sources(tmp_path: Path) -> None:
    bench = new_bench(tmp_path, covers=FakeCovers({"openlibrary:OL1W": JPEG + b"source"}))
    download_id = audiobook(bench, tmp_path)

    await bench.service.round()

    folder = bench.roots["audiobook"] / "David Goggins" / "Ne cède jamais" / "01 - Ne cède jamais"
    assert sorted(p.name for p in folder.iterdir()) == [
        "Ne cède jamais - T01 - Ne cède jamais.m4b",
        "cover.jpg",
    ]
    assert (folder / "Ne cède jamais - T01 - Ne cède jamais.m4b").read_bytes() == b"[1][2][3]"
    assert (folder / "cover.jpg").read_bytes() == JPEG + b"source"
    [(tracks, title, cover, _)] = bench.tools.merged
    assert tracks == [f"Ne cède jamais - T01 - Ne cède jamais - {n:03d}.mp3" for n in (1, 2, 3)]
    assert (title, cover) == ("Ne cède jamais", folder / "cover.jpg")
    assert bench.downloads.rows[download_id].stage == "placed"
    assert [f.path for f in bench.shelf.files] == [
        str(folder / "Ne cède jamais - T01 - Ne cède jamais.m4b")
    ]
    # The tracks of the torrent are still there: it seeds on.
    assert len(list((tmp_path / "torrents" / "audiobook").rglob("*.mp3"))) == 3


@pytest.mark.anyio
async def test_a_merge_that_fails_leaves_the_tracks_and_says_so(tmp_path: Path) -> None:
    bench = new_bench(tmp_path, tools=FakeTools(fails=True))
    download_id = audiobook(bench, tmp_path, picture=True)

    await bench.service.round()

    row = bench.downloads.rows[download_id]
    assert (row.stage, row.unplaced) == ("unplaced", "merge_failed")
    folder = bench.roots["audiobook"] / "David Goggins" / "Ne cède jamais" / "01 - Ne cède jamais"
    assert len(list(folder.glob("*.mp3"))) == 3
    assert (folder / "cover.jpg").read_bytes() == JPEG + b"torrent"
    [failed] = bench.journal.of("failed")
    assert failed.facts["what"] == "merge_failed"


@pytest.mark.anyio
async def test_the_metadata_of_the_files_placed_is_locked_once_jellyfin_has_them(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path)
    completed(bench, berserk(bench, tmp_path))
    await bench.service.round()
    assert await bench.service.lock() == 0
    for n in (41, 42):
        bench.jellyfin.items[f"b{n}"] = {
            "Id": f"b{n}",
            "Type": "Book",
            "Name": f"Tome {n}",
            "LibraryId": "lib-manga",
            "Path": f"/files/comics/Berserk/Berserk - T{n}.cbz",
        }

    assert await bench.service.lock() == 2

    item = bench.jellyfin.items["b41"]
    assert item["Name"] == "Berserk - T41"
    assert (item["SeriesName"], item["IndexNumber"]) == ("Berserk", 41)
    assert item["People"] == [{"Name": "Kentaro Miura", "Type": "Author", "Role": ""}]
    assert item["LockedFields"] == ["Cast", "Name"]
    assert await bench.service.lock() == 0


@pytest.mark.anyio
async def test_a_cover_the_page_chose_is_written_in_its_series(tmp_path: Path) -> None:
    bench = new_bench(tmp_path)
    (bench.roots["manga"] / "Gunnm").mkdir()
    bench.shelf.add_task("cover", "/files/comics/Gunnm", JPEG + b"chosen", 0)
    bench.shelf.add_task("cover", "/files/comics/../../etc", JPEG, 0)

    await bench.service.run_tasks()

    assert (bench.roots["manga"] / "Gunnm" / "cover.jpg").read_bytes() == JPEG + b"chosen"
    assert sorted(state for _, state in bench.shelf.tasks.values()) == ["done", "failed"]


@pytest.mark.anyio
async def test_a_download_copied_says_so_on_the_page_and_in_the_journal(tmp_path: Path) -> None:
    bench = new_bench(tmp_path, mode="copy")
    torrent = berserk(bench, tmp_path)
    download = completed(bench, torrent)

    await bench.service.round()

    row = bench.downloads.rows[download.id]
    assert (row.stage, row.copied) == ("placed", True)
    placed = bench.roots["manga"] / "Berserk" / "Berserk - T41.cbz"
    source = torrent / "Berserk.T41.FRENCH.CBZ.cbz"
    assert placed.stat().st_ino != source.stat().st_ino
    assert [f.copied_from for f in bench.shelf.files] == [
        str(source),
        str(torrent / "Berserk.T42.FRENCH.CBZ.cbz"),
    ]
    [event] = bench.journal.of("placed")
    assert event.facts["copied"] is True


@pytest.mark.anyio
async def test_a_mode_it_does_not_know_hardlinks(tmp_path: Path) -> None:
    bench = new_bench(tmp_path, mode="move")
    torrent = berserk(bench, tmp_path)
    download = completed(bench, torrent)

    await bench.service.round()

    assert bench.downloads.rows[download.id].copied is False
    placed = bench.roots["manga"] / "Berserk" / "Berserk - T41.cbz"
    assert placed.stat().st_ino == (torrent / "Berserk.T41.FRENCH.CBZ.cbz").stat().st_ino
    assert "copied" not in bench.journal.of("placed")[0].facts


@pytest.mark.anyio
async def test_an_adoption_renames_its_files_never_over_one_and_records_them(
    tmp_path: Path,
) -> None:
    bench = new_bench(tmp_path)
    folder = bench.roots["manga"] / "Berserk"
    folder.mkdir()
    for name in ("berserk_v03.cbz", "extra.cbz", "Berserk - T04.cbz"):
        (folder / name).write_bytes(name.encode())

    def adopted(name: str, volume: int) -> PlacedFile:
        return PlacedFile(
            download_id=None,
            kind="manga",
            work_id="mangaupdates:1",
            series="Berserk",
            author="",
            volume=volume,
            chapter=None,
            path=str(folder / name),
        )

    order = AdoptOrder(
        series_id="berserk",
        files=(adopted("berserk_v03.cbz", 3), adopted("extra.cbz", 4)),
        targets=(str(folder / "Berserk - T03.cbz"), str(folder / "Berserk - T04.cbz")),
    )
    bench.shelf.add_adoption(order, 0)
    bench.jellyfin.items["berserk"] = {"Id": "berserk", "Type": "Folder"}

    await bench.service.run_tasks()

    assert sorted(p.name for p in folder.iterdir()) == [
        "Berserk - T03.cbz",
        "Berserk - T04.cbz",
        "extra.cbz",
    ]
    # The name taken: both files left as they are.
    assert (folder / "Berserk - T04.cbz").read_bytes() == b"Berserk - T04.cbz"
    assert (folder / "Berserk - T03.cbz").read_bytes() == b"berserk_v03.cbz"
    assert [(f.path, f.volume) for f in bench.shelf.files] == [
        (str(folder / "Berserk - T03.cbz"), 3),
        (str(folder / "extra.cbz"), 4),
    ]
    assert [state for _, state in bench.shelf.tasks.values()] == ["done"]
    assert [item_id for item_id, _ in bench.jellyfin.refreshed] == ["berserk"]
