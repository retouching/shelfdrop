from pathlib import Path

from shelfdrop.placement.scan import scan_library
from tests.unit.placement.support import cbz


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def test_a_manga_at_the_root_out_of_its_names_or_in_chapters_is_found(tmp_path: Path) -> None:
    root = tmp_path / "comics"
    touch(root / "Berserk T01.cbz")
    touch(root / "Berserk" / "Berserk - T01.cbz")
    touch(root / "Berserk" / "Berserk T02.cbz")
    touch(root / "Berserk" / "cover.jpg")
    touch(root / "Chainsaw Man" / "Chainsaw Man - T22.cbz")
    for n in (230, 231):
        cbz(root / "Chainsaw Man" / f"Chapitre {n}.cbz", ["1.jpg"])
    placed = touch(root / "Chainsaw Man" / "Chainsaw Man - Ch. 232.cbz")

    found = scan_library("manga", root, {str(placed)}, merge_mp3=True)

    assert [(i.name, i.state, i.reason) for i in found] == [
        ("Berserk T02.cbz", "misplaced", "naming"),
        ("Berserk T01.cbz", "misplaced", "root"),
        ("Chainsaw Man", "chapters", "chapters"),
    ]
    chapters = found[-1]
    assert (chapters.chapters, chapters.existing, chapters.series) == (
        (230.0, 231.0),
        (22,),
        "Chainsaw Man",
    )
    assert chapters.origin == "library"


def test_books_out_of_their_folders_and_tracks_not_merged_are_found(tmp_path: Path) -> None:
    ebooks = tmp_path / "ebooks"
    touch(ebooks / "Goggins.epub")
    touch(ebooks / "David Goggins" / "Never Finished.epub")
    touch(ebooks / "Robin Hobb" / "Les Aventuriers" / "01 - Le Vaisseau" / "x - T01.epub")
    audio = tmp_path / "audiobooks"
    for n in (1, 2):
        touch(audio / "Margot" / "La Memoire" / "01 - Le dragon" / f"t - {n:03d}.mp3")
    touch(audio / "Margot" / "Autre" / "01 - Un" / "Autre - T01 - Un.m4b")

    books = scan_library("ebook", ebooks, set(), merge_mp3=True)
    tracks = scan_library("audiobook", audio, set(), merge_mp3=True)
    unmerged = scan_library("audiobook", audio, set(), merge_mp3=False)

    assert [(i.name, i.reason) for i in books] == [
        ("Never Finished.epub", "naming"),
        ("Goggins.epub", "root"),
    ]
    [folder] = tracks
    assert (folder.name, folder.reason, len(folder.files), folder.author, folder.series) == (
        "01 - Le dragon",
        "tracks",
        2,
        "Margot",
        "La Memoire",
    )
    assert unmerged == []


def test_a_library_missing_finds_nothing(tmp_path: Path) -> None:
    assert scan_library("manga", tmp_path / "none", set(), merge_mp3=True) == []
