import zipfile
from pathlib import Path

import pytest

from shelfdrop.placement.uploads import (
    ZipRefusedError,
    lay_upload,
    open_zip,
    remove_empty,
    safe_entry,
    upload_items,
)


def test_each_book_sent_is_a_file_and_the_tracks_of_a_folder_one() -> None:
    items = upload_items(
        "Livres.zip",
        [
            ("/data/envois/3/Livres/La Mémoire des os/01.mp3", 10),
            ("/data/envois/3/Livres/La Mémoire des os/02.mp3", 20),
            ("/data/envois/3/Livres/Berserk T01.cbz", 5),
            ("/data/envois/3/Livres/Ne cède jamais.epub", 7),
            ("/data/envois/3/Livres/cover.jpg", 1),
        ],
    )

    assert sorted((i.name, i.kind, i.size, len(i.files)) for i in items) == [
        ("Berserk T01.cbz", "manga", 5, 1),
        ("La Mémoire des os", "audiobook", 30, 2),
        ("Ne cède jamais.epub", "ebook", 7, 1),
    ]
    assert {(i.origin, i.state, i.reason, i.download_id) for i in items} == {
        ("upload", "unlinked", "upload", None)
    }


def test_a_file_sent_with_no_book_is_one_file_of_no_kind() -> None:
    [item] = upload_items("Notes.zip", [("/data/envois/4/Notes.zip", 9)])
    assert (item.kind, item.path, item.size) == (None, "/data/envois/4/Notes.zip", 9)
    assert upload_items("Empty.zip", []) == []


@pytest.mark.parametrize("name", ["../x.cbz", "/etc/x.cbz", "a/", ".hidden/x.cbz", "__MACOSX/x"])
def test_a_zip_entry_out_of_its_folder_is_left(name: str) -> None:
    assert safe_entry(name) is None


def test_a_zip_sent_is_moved_and_opened_next_to_it(tmp_path: Path) -> None:
    source = tmp_path / "data" / "Pistes.zip"
    source.parent.mkdir()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("Tome 1/001.mp3", b"one")
        archive.writestr("Tome 1/002.mp3", b"two")
        archive.writestr("../evil.mp3", b"no")

    files = lay_upload(source, tmp_path / "envois" / "7")

    folder = tmp_path / "envois" / "7" / "Pistes" / "Tome 1"
    assert files == [(str(folder / "001.mp3"), 3), (str(folder / "002.mp3"), 3)]
    assert not source.exists()
    assert not (tmp_path / "envois" / "7" / "Pistes.zip").exists()
    assert not (tmp_path / "envois" / "evil.mp3").exists()


def test_a_zip_that_does_not_open_stays_as_it_is(tmp_path: Path) -> None:
    source = tmp_path / "Broken.zip"
    source.write_bytes(b"not a zip")

    files = lay_upload(source, tmp_path / "envois")

    assert files == [(str(tmp_path / "envois" / "Broken.zip"), 9)]


def test_a_zip_too_big_once_opened_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "Big.zip"
    with zipfile.ZipFile(archive, "w") as opened:
        opened.writestr("a.cbz", b"x" * 100)
    monkeypatch.setattr("shelfdrop.placement.uploads.UNZIPPED_MAX_BYTES", 10)

    with pytest.raises(ZipRefusedError):
        open_zip(archive)


def test_the_empty_folders_of_the_uploads_go(tmp_path: Path) -> None:
    (tmp_path / "1" / "a").mkdir(parents=True)
    (tmp_path / "2").mkdir()
    (tmp_path / "2" / "kept.epub").write_bytes(b"x")

    remove_empty(tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["2"]
