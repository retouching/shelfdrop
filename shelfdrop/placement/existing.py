"""What the shelf already holds (plan section 3, point 4 bis): the volumes and the chapters of a
series folder, read from the names of its files, and what a release adds to them. Pure: the
caller lists the folder."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePath

from shelfdrop.placement.naming import COMIC_EXTENSIONS, file_volume, stated_volume
from shelfdrop.placement.types import ShelfContent
from shelfdrop.releases.guess import chapters_of


def content_of(names: Iterable[str]) -> ShelfContent:
    """The volumes and the chapters of the files `names` of a series folder: '... - T03.cbz' is
    a volume, '... - T23 - Ch. 206.cbz' and '... - Ch. 230.cbz' chapters; a chapter range
    counts each whole chapter of it."""
    volumes: set[int] = set()
    chapters: set[float] = set()
    for name in names:
        path = PurePath(name)
        if path.suffix.lower() not in COMIC_EXTENSIONS:
            continue
        found = chapters_of(path.stem)
        if found is not None:
            last = found.last if found.last is not None else found.first
            chapters.add(found.first)
            chapters.update(float(n) for n in range(int(found.first) + 1, int(last) + 1))
            if last != int(last):
                chapters.add(last)
            continue
        volume = file_volume(path.stem)
        if volume is not None:
            volumes.add(volume)
    return ShelfContent(volumes=frozenset(volumes), chapters=frozenset(chapters))


@dataclass(frozen=True, kw_only=True)
class Split:
    """The files of a release against the shelf: those to add, those already there."""

    added: tuple[tuple[str, int], ...]
    """Each file to add and its volume."""
    present: tuple[int, ...]
    """The volumes already on the shelf: never written again."""


def split_volumes(files: Sequence[tuple[str, int]], shelf: ShelfContent) -> Split:
    """The files `(name, volume)` of a release, the volumes the shelf has set aside; two files
    of one volume, the first alone."""
    added: list[tuple[str, int]] = []
    present: list[int] = []
    seen: set[int] = set()
    for name, volume in files:
        if volume in shelf.volumes:
            present.append(volume)
        elif volume not in seen:
            added.append((name, volume))
        seen.add(volume)
    return Split(added=tuple(added), present=tuple(sorted(set(present))))


def is_chapters_release(names: Sequence[str], known_volumes: int | None) -> bool:
    """A release in chapters: most of its files name a chapter and no volume, or it holds far
    more files than the work has volumes (500 files for 40 volumes)."""
    books = [n for n in names if PurePath(n).suffix.lower() in COMIC_EXTENSIONS]
    if not books:
        return False
    in_chapters = sum(
        1
        for n in books
        if chapters_of(PurePath(n).stem) is not None and stated_volume(PurePath(n).stem) is None
    )
    if in_chapters * 2 > len(books):
        return True
    return known_volumes is not None and known_volumes > 0 and len(books) > 2 * known_volumes + 2


def complete_volumes(
    chapters: Iterable[float], volumes: dict[int, tuple[float, float]]
) -> list[int]:
    """The volumes whose every whole chapter (from `first` to `last`, `volumes[n]`) is in
    `chapters`: they can be merged into one CBZ."""
    have = set(chapters)
    return sorted(
        number
        for number, (first, last) in volumes.items()
        if all(float(c) in have for c in range(int(first), int(last) + 1))
    )
