"""shelfdrop.placement.comics: the pages of a CBZ, its first page, and chapters merged into one
volume with its cover and its ComicInfo.xml."""

from pathlib import Path

import pytest

from shelfdrop.placement.comics import ArchiveError, first_page, merge_chapters
from shelfdrop.placement.types import ComicInfo
from tests.unit.placement.support import JPEG, cbz, pages_in


def test_the_first_page_is_the_first_in_the_natural_order(tmp_path: Path) -> None:
    volume = cbz(tmp_path / "v.cbz", ["p10.jpg", "p2.jpg", "__MACOSX/p1.jpg", ".p0.jpg"])

    data, extension = first_page(volume)

    assert data == JPEG + b"p2.jpg"
    assert extension == ".jpg"
    with pytest.raises(ArchiveError):
        first_page(cbz(tmp_path / "empty.cbz", ["ComicInfo.xml"]))


def test_chapters_merge_in_their_order_behind_the_cover(tmp_path: Path) -> None:
    first = cbz(tmp_path / "Ch. 206.cbz", ["10.jpg", "2.jpg"])
    second = cbz(tmp_path / "Ch. 206.5.cbz", ["1.png"])
    out = tmp_path / "Chainsaw Man - T23.cbz"
    info = ComicInfo(
        series="Chainsaw Man", number=23, writers=("Tatsuki Fujimoto",), summary="Denji & co"
    )

    written = merge_chapters([first, second], out, info, (b"cover", ".jpg"))

    assert written == 4
    pages = pages_in(out)
    assert [name for name, _ in pages] == [
        "0000.jpg",
        "0001.jpg",
        "0002.jpg",
        "0003.png",
        "ComicInfo.xml",
    ]
    assert [data for _, data in pages[:4]] == [
        b"cover",
        JPEG + b"2.jpg",
        JPEG + b"10.jpg",
        JPEG + b"1.png",
    ]
    xml = pages[4][1].decode()
    assert "<Series>Chainsaw Man</Series>" in xml
    assert "<Number>23</Number>" in xml
    assert "<Writer>Tatsuki Fujimoto</Writer>" in xml
    assert "<Summary>Denji &amp; co</Summary>" in xml
    assert "<PageCount>4</PageCount>" in xml
    assert '<Page Image="0" Type="FrontCover" />' in xml
    assert not (tmp_path / "Chainsaw Man - T23.cbz.part").exists()


def test_a_volume_already_there_is_never_replaced(tmp_path: Path) -> None:
    chapter = cbz(tmp_path / "Ch. 1.cbz", ["1.jpg"])
    out = tmp_path / "Berserk - T01.cbz"
    out.write_bytes(b"kept")

    with pytest.raises(FileExistsError):
        merge_chapters([chapter], out, ComicInfo(series="Berserk", number=1), None)

    assert out.read_bytes() == b"kept"


def test_without_a_cover_the_first_page_comes_first_and_is_declared_none(tmp_path: Path) -> None:
    chapter = cbz(tmp_path / "Ch. 1.cbz", ["1.jpg", "2.jpg"])
    out = tmp_path / "Berserk - T01.cbz"

    merge_chapters([chapter], out, ComicInfo(series="Berserk", number=1), None)

    names = [name for name, _ in pages_in(out)]
    assert names[:2] == ["0000.jpg", "0001.jpg"]
    assert "FrontCover" not in dict(pages_in(out))["ComicInfo.xml"].decode()
