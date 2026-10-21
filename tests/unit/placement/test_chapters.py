import os
import xml.etree.ElementTree as ET  # the ComicInfo.xml the test wrote itself
from pathlib import Path

import pytest

from shelfdrop.placement.chapters import place_chapter, place_chapters, place_volume
from shelfdrop.placement.layout import NotPlacedError
from shelfdrop.placement.types import (
    ChapterRequest,
    ChaptersRequest,
    VolumeRange,
    VolumeRequest,
)
from tests.unit.placement.support import JPEG, cbz, pages_in

SERIES = "Chainsaw Man"


def chapters(folder: Path, numbers: list[str]) -> list[str]:
    return [
        str(cbz(folder / f"{SERIES} - Ch. {n} [Scan FR].cbz", [f"{n}-2.jpg", f"{n}-1.jpg"]))
        for n in numbers
    ]


def request(*volumes: VolumeRange, rest: str = "keep") -> ChaptersRequest:
    return ChaptersRequest(
        work_id="mangaupdates:1",
        series=SERIES,
        author="Tatsuki Fujimoto",
        summary="Denji",
        volumes=volumes,
        rest="place" if rest == "place" else "keep",
    )


def test_a_volume_is_linked_under_its_name_and_never_over_a_file_there(tmp_path: Path) -> None:
    root = tmp_path / "comics"
    source = cbz(tmp_path / "dl" / "Chainsaw Man T23 [FR].cbz", ["1.jpg"])
    asked = VolumeRequest(
        kind="manga", work_id=None, series=SERIES, author="Tatsuki Fujimoto", volume=23
    )

    hand = place_volume([str(source)], asked, root, covers=True)

    target = root / SERIES / f"{SERIES} - T23.cbz"
    assert os.path.samefile(source, target)
    assert [(f.volume, f.path) for f in hand.laid.files] == [(23, str(target))]
    assert (root / SERIES / "cover.jpg").read_bytes() == JPEG + b"1.jpg"
    other = cbz(tmp_path / "dl" / "other.cbz", ["1.jpg"])
    with pytest.raises(NotPlacedError) as refused:
        place_volume([str(other)], asked, root, covers=True)
    assert refused.value.reason == "exists"


def test_a_file_of_chapters_takes_its_range_and_its_volume(tmp_path: Path) -> None:
    source = cbz(tmp_path / "dl" / "Chainsaw Man Ch. 233-236.cbz", ["1.jpg"])
    asked = ChapterRequest(work_id=None, series=SERIES, author="", first=233, last=236)

    hand = place_chapter([str(source)], asked, tmp_path / "comics", covers=False)

    [placed] = hand.laid.files
    assert Path(placed.path).name == f"{SERIES} - Ch. 233-236.cbz"
    assert (placed.volume, placed.chapter) == (None, 233)


def test_a_complete_volume_is_merged_an_incomplete_one_linked_the_rest_kept(
    tmp_path: Path,
) -> None:
    release = chapters(tmp_path / "dl", ["206", "207", "207.5", "208", "215", "217", "230"])
    root = tmp_path / "comics"

    hand = place_chapters(
        release,
        request(
            VolumeRange(volume=23, first=206, last=208), VolumeRange(volume=24, first=215, last=217)
        ),
        root,
        covers=True,
    )

    folder = root / SERIES
    assert sorted(p.name for p in folder.iterdir()) == [
        f"{SERIES} - T23.cbz",
        f"{SERIES} - T24 - Ch. 215.cbz",
        f"{SERIES} - T24 - Ch. 217.cbz",
        "cover.jpg",
    ]
    pages = pages_in(folder / f"{SERIES} - T23.cbz")
    # The cover (the first page of the first chapter), then the pages of each chapter in order.
    assert [data.removeprefix(JPEG) for _, data in pages[:-1]] == [
        b"206-1.jpg",
        b"206-1.jpg",
        b"206-2.jpg",
        b"207-1.jpg",
        b"207-2.jpg",
        b"207.5-1.jpg",
        b"207.5-2.jpg",
        b"208-1.jpg",
        b"208-2.jpg",
    ]
    info = ET.fromstring(pages[-1][1])  # noqa: S314  # written by the test
    assert (info.findtext("Series"), info.findtext("Number"), info.findtext("PageCount")) == (
        SERIES,
        "23",
        "9",
    )
    assert info.findtext("Summary") == "Denji"
    assert [(f.volume, f.chapter) for f in hand.laid.files] == [(23, None), (24, 215), (24, 217)]
    assert hand.left == (release[-1],)
    assert release[-1] not in hand.used


def test_the_rest_is_placed_without_a_volume_and_a_volume_there_is_left(tmp_path: Path) -> None:
    root = tmp_path / "comics"
    cbz(root / SERIES / f"{SERIES} - T23.cbz", ["mine.jpg"])
    release = chapters(tmp_path / "dl", ["206", "230"])

    hand = place_chapters(
        release, request(VolumeRange(volume=23, first=206, last=206), rest="place"), root, False
    )

    assert pages_in(root / SERIES / f"{SERIES} - T23.cbz")[0][1] == JPEG + b"mine.jpg"
    assert [Path(f.path).name for f in hand.laid.files] == [f"{SERIES} - Ch. 230.cbz"]
    assert hand.left == ()


def test_a_volume_complete_with_the_loose_chapters_of_the_shelf_is_merged_and_they_go(
    tmp_path: Path,
) -> None:
    root = tmp_path / "comics"
    loose = cbz(root / SERIES / f"{SERIES} - T23 - Ch. 206.cbz", ["206-1.jpg"])
    release = chapters(tmp_path / "dl", ["207"])

    hand = place_chapters(
        release, request(VolumeRange(volume=23, first=206, last=207)), root, False
    )

    assert not loose.exists()
    assert hand.removed == (str(loose),)
    assert len(pages_in(root / SERIES / f"{SERIES} - T23.cbz")) == 1 + 3 + 1


def test_a_volume_there_is_replaced_only_when_asked(tmp_path: Path) -> None:
    root = tmp_path / "comics"
    cbz(root / SERIES / f"{SERIES} - T23.cbz", ["mine.jpg"])
    release = chapters(tmp_path / "dl", ["206"])

    place_chapters(
        release, request(VolumeRange(volume=23, first=206, last=206, replace=True)), root, False
    )

    assert pages_in(root / SERIES / f"{SERIES} - T23.cbz")[0][1] == JPEG + b"206-1.jpg"
    assert sorted(p.name for p in (root / SERIES).iterdir()) == [f"{SERIES} - T23.cbz"]
