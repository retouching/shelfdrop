"""shelfdrop.placement.layout: the files of a download on the shelf, in hardlinks, what is there
left as it is."""

import os
from pathlib import Path

import pytest

from shelfdrop.placement.layout import NotPlacedError, Order, lay_audio, place_books, place_comics
from shelfdrop.releases.types import Volumes
from tests.unit.placement.support import JPEG, cbz


def order(**fields: object) -> Order:
    values: dict[str, object] = {
        "download_id": 7,
        "kind": "manga",
        "work_id": "mangaupdates:1",
        "series": "Berserk",
        "author": "Kentaro Miura",
        "release": "Berserk.T40-T42.FRENCH.CBZ",
        "volumes": Volumes(kind="range", first=40, last=42),
    }
    values.update(fields)
    return Order(**values)  # type: ignore[arg-type]  # the fields named by each test


def test_the_volumes_missing_are_linked_and_the_others_left(tmp_path: Path) -> None:
    torrent = tmp_path / "torrents" / "Berserk T40-T42"
    files = [cbz(torrent / f"Berserk T{n}.cbz", ["1.jpg"]) for n in (40, 41, 42)]
    root = tmp_path / "comics"
    (root / "Berserk").mkdir(parents=True)
    (root / "Berserk" / "Berserk - T40.cbz").write_bytes(b"mine")

    laid = place_comics(order(), files, root, True)

    assert laid.volumes == (41, 42)
    assert laid.present == (40,)
    assert (root / "Berserk" / "Berserk - T40.cbz").read_bytes() == b"mine"
    placed = root / "Berserk" / "Berserk - T41.cbz"
    # A hardlink: the torrent seeds on, without a second copy.
    assert os.stat(placed).st_ino == os.stat(files[1]).st_ino
    assert [f.path for f in laid.files] == [
        str(placed),
        str(root / "Berserk" / "Berserk - T42.cbz"),
    ]
    # The series had no cover: the first page of its first volume that is a CBZ.
    assert (root / "Berserk" / "cover.jpg").read_bytes() == laid.cover == JPEG + b"1.jpg"


def test_the_cover_of_a_series_is_the_first_page_of_its_first_volume(tmp_path: Path) -> None:
    files = [
        cbz(tmp_path / "t" / "Gunnm T02.cbz", ["b.jpg"]),
        cbz(tmp_path / "t" / "Gunnm T01.cbz", ["a.jpg"]),
    ]

    laid = place_comics(
        order(series="Gunnm", volumes=Volumes(kind="unknown")), files, tmp_path / "c", True
    )

    assert laid.cover == JPEG + b"a.jpg"
    assert (tmp_path / "c" / "Gunnm" / "cover.jpg").read_bytes() == JPEG + b"a.jpg"


def test_one_file_without_a_number_is_the_volume_of_its_release(tmp_path: Path) -> None:
    file = cbz(tmp_path / "t" / "Look Back.cbz", ["1.jpg"])

    laid = place_comics(
        order(series="Look Back", volumes=Volumes(kind="single", first=1, last=1)),
        [file],
        tmp_path / "c",
        False,
    )

    assert laid.volumes == (1,)
    assert (tmp_path / "c" / "Look Back" / "Look Back - T01.cbz").is_file()
    assert laid.cover is None


@pytest.mark.parametrize(
    ("names", "reason"),
    [
        (
            ["Chainsaw Man - Ch. 1.cbz", "Chainsaw Man - Ch. 2.cbz", "Chainsaw Man - Ch. 3.5.cbz"],
            "chapters",
        ),
        (["Berserk bonus.cbz", "Berserk extras.cbz"], "no_volume"),
        (["readme.txt"], "no_files"),
    ],
)
def test_what_cannot_be_placed_alone_goes_to_ranger(
    tmp_path: Path, names: list[str], reason: str
) -> None:
    files = [cbz(tmp_path / "t" / n, ["1.jpg"]) for n in names]

    with pytest.raises(NotPlacedError) as refused:
        place_comics(order(volumes=Volumes(kind="unknown")), files, tmp_path / "c", True)

    assert refused.value.reason == reason
    assert not (tmp_path / "c").exists() or not any((tmp_path / "c").rglob("*.cbz"))


def test_the_volumes_read_are_placed_and_the_books_without_one_left(tmp_path: Path) -> None:
    torrent = tmp_path / "t" / "Berserk"
    files = [cbz(torrent / n, ["1.jpg"]) for n in ("Berserk T41.cbz", "Berserk bonus.cbz")]

    laid = place_comics(order(volumes=Volumes(kind="unknown")), files, tmp_path / "c", False)

    assert laid.volumes == (41,)
    assert laid.unknown == (str(files[1]),)
    assert sorted(p.name for p in (tmp_path / "c" / "Berserk").iterdir()) == ["Berserk - T41.cbz"]


def test_the_books_of_a_pack_without_a_volume_are_left(tmp_path: Path) -> None:
    torrent = tmp_path / "t" / "Dune"
    for folder in ("Tome 1", "Tome 2", "Bonus"):
        (torrent / folder).mkdir(parents=True)
        (torrent / folder / "book.epub").write_bytes(folder.encode())
    pack = order(
        kind="ebook",
        series="Dune",
        author="Frank Herbert",
        release="Dune.Integrale.FRENCH.EPUB",
        volumes=Volumes(kind="range", first=1, last=2),
    )

    laid = place_books(pack, sorted(torrent.rglob("*.epub")), tmp_path / "ebooks")

    assert laid.volumes == (1, 2)
    assert laid.unknown == (str(torrent / "Bonus" / "book.epub"),)
    with pytest.raises(NotPlacedError) as refused:
        place_books(pack, [torrent / "Bonus" / "book.epub"], tmp_path / "x")
    assert refused.value.reason == "no_volume"


def test_a_book_goes_under_its_author_its_series_and_its_volume(tmp_path: Path) -> None:
    torrent = tmp_path / "t" / "Plus.Rien.Ne.Pourra.Me.Blesser"
    torrent.mkdir(parents=True)
    (torrent / "book.epub").write_bytes(b"epub")
    (torrent / "book.pdf").write_bytes(b"pdf")
    (torrent / "cover.jpg").write_bytes(b"jpg")
    book = order(
        kind="ebook",
        series="Plus rien ne pourra me blesser",
        author="David Goggins",
        release="Plus.Rien.Ne.Pourra.Me.Blesser.David.Goggins.FRENCH.EPUB",
        volumes=Volumes(kind="single", first=1, last=1),
    )

    laid = place_books(book, sorted(torrent.iterdir()), tmp_path / "ebooks")

    folder = tmp_path / "ebooks" / "David Goggins" / "Plus rien ne pourra me blesser"
    folder /= "01 - Plus rien ne pourra me blesser"
    assert sorted(p.name for p in folder.iterdir()) == [
        "Plus rien ne pourra me blesser - T01 - Plus rien ne pourra me blesser.epub",
        "Plus rien ne pourra me blesser - T01 - Plus rien ne pourra me blesser.pdf",
    ]
    assert laid.volumes == (1,)
    # Placed again: the volume is there, nothing is written.
    again = place_books(book, sorted(torrent.iterdir()), tmp_path / "ebooks")
    assert (again.files, again.present) == ((), (1,))
    with pytest.raises(NotPlacedError) as refused:
        place_books(order(kind="ebook", author=" "), sorted(torrent.iterdir()), tmp_path / "x")
    assert refused.value.reason == "unknown_author"


def test_the_tracks_of_an_audiobook_are_linked_in_their_order_to_merge(tmp_path: Path) -> None:
    torrent = tmp_path / "t" / "Margot Looten - Le dragon et l'oiseau"
    torrent.mkdir(parents=True)
    for n in (10, 2, 1):
        (torrent / f"Le dragon et l'oiseau - {n:03d}.mp3").write_bytes(b"mp3-%d" % n)
    (torrent / "folder.jpg").write_bytes(b"jpg")
    book = order(
        kind="audiobook",
        series="La Mémoire des os",
        author="Margot Looten",
        release="Margot Looten - Le dragon et l'oiseau",
        volumes=Volumes(kind="single", first=1, last=1),
    )

    laid, merges = lay_audio(book, sorted(torrent.iterdir()), tmp_path / "audio", True)

    [merge] = merges
    assert [t.name for t in merge.tracks] == [
        f"La Mémoire des os - T01 - La Mémoire des os - {n:03d}.mp3" for n in (1, 2, 3)
    ]
    assert [t.read_bytes() for t in merge.tracks] == [b"mp3-1", b"mp3-2", b"mp3-10"]
    assert merge.target.name == "La Mémoire des os - T01 - La Mémoire des os.m4b"
    assert merge.cover is not None
    assert merge.cover.name == "cover.jpg"
    assert laid.files == ()
