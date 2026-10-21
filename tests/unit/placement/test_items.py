from shelfdrop.downloads.types import Download
from shelfdrop.placement.items import chapter_files, chapter_numbers, items_of
from shelfdrop.releases.types import Volumes
from shelfdrop.works.types import Kind


def download(kind: Kind = "manga", volumes: Volumes | None = None) -> Download:
    return Download(
        id=7,
        info_hash="a" * 40,
        release_id="0123456789abcdef",
        title="Chainsaw Man - Ch. 001-232 [Scan FR]",
        indexer="Nyaa.si",
        size=4100,
        download_url=None,
        work_id="mangaupdates:1",
        work_name="Chainsaw Man",
        author="Tatsuki Fujimoto",
        series="Chainsaw Man",
        volumes=volumes or Volumes(kind="unknown"),
        kind=kind,
        mode="auto",
        category=kind,
        stage="unplaced",
        failure=None,
        attempts=1,
        created_at=0,
        created_by="sylvain",
        added_at=0,
        unplaced="chapters",
    )


def test_the_chapters_of_names_count_each_one_of_a_range_and_the_halves() -> None:
    names = ["CSM - Ch. 233-236.cbz", "CSM - Ch. 10.5.cbz", "CSM - Ch. 10.cbz", "cover.jpg"]

    assert chapter_numbers(names) == (10.0, 10.5, 233.0, 234.0, 235.0, 236.0)
    assert chapter_files(names)[235.0] == "CSM - Ch. 233-236.cbz"


def test_a_release_in_chapters_is_one_file_of_ranger_with_its_chapters() -> None:
    torrent = "/data/torrents/manga/Chainsaw Man"
    files = [(f"{torrent}/Chainsaw Man - Ch. {n}.cbz", 10) for n in ("230", "231", "231.5")]

    [item] = items_of(download(), torrent, files, [1, 2], [229.0])

    assert (item.state, item.reason, item.path, item.size) == ("chapters", "chapters", torrent, 30)
    assert item.loose == (229.0,)
    assert item.chapters == (230.0, 231.0, 231.5)
    assert (item.series, item.existing, item.work_id) == ("Chainsaw Man", (1, 2), "mangaupdates:1")


def test_each_volume_of_another_release_is_one_file_and_a_torrent_without_files_one() -> None:
    torrent = "/data/torrents/manga/Berserk"
    files = [(f"{torrent}/Berserk {n}.cbz", 5) for n in ("T41", "T42")] + [(f"{torrent}/x.nfo", 1)]

    items = items_of(download(volumes=Volumes(kind="range", first=41, last=42)), torrent, files, [])
    empty = items_of(download(), torrent, [], [])

    assert [(i.name, i.files, i.state) for i in items] == [
        ("Berserk T41.cbz", (f"{torrent}/Berserk T41.cbz",), "unlinked"),
        ("Berserk T42.cbz", (f"{torrent}/Berserk T42.cbz",), "unlinked"),
    ]
    assert [(i.files, i.size) for i in empty] == [((), 4100)]


def test_the_tracks_of_one_folder_of_an_audiobook_are_one_file() -> None:
    torrent = "/data/torrents/audiobook/Never Finished"
    files = [(f"{torrent}/CD1/Never Finished - {n:03d}.mp3", 3) for n in (1, 2)]
    files.append((f"{torrent}/Bonus.m4b", 4))

    items = items_of(download("audiobook"), torrent, files, [])

    assert [(i.name, i.path, len(i.files), i.size) for i in items] == [
        ("CD1", f"{torrent}/CD1", 2, 6),
        ("Bonus.m4b", f"{torrent}/Bonus.m4b", 1, 4),
    ]
