"""The files of Ranger placed on the shelf: one volume of a
manga, one file of chapters, and a release in chapters linked to its volumes: each complete
volume merged into one CBZ (its cover, its pages in the order of the chapters, its
`ComicInfo.xml`), the chapters of an incomplete one placed as they are, the rest without a
volume or kept. A file there is never replaced, but a volume whose replacement the page asked.
Runs in the threadpool: file system alone."""

import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from shelfdrop.placement.comics import ArchiveError, first_page, merge_chapters
from shelfdrop.placement.existing import content_of
from shelfdrop.placement.items import chapter_files
from shelfdrop.placement.layout import Laid, NotPlacedError, copy_source, lay_file, series_cover
from shelfdrop.placement.naming import (
    COMIC_EXTENSIONS,
    chapter_name,
    comic_name,
    safe,
)
from shelfdrop.placement.shelf import make_folder, names_in
from shelfdrop.placement.types import (
    ChapterRequest,
    ChaptersRequest,
    ComicInfo,
    Outcome,
    PlacedFile,
    PlaceMode,
    VolumeRequest,
)
from shelfdrop.releases.guess import chapters_of


@dataclass(frozen=True, kw_only=True)
class HandLaid:
    """What a file of Ranger put on the shelf, the files of it now there under another name or
    merged (removed when they come from the libraries), those left to place, and the chapters
    of the shelf merged away."""

    laid: Laid
    used: tuple[str, ...]
    left: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()


def shelf_file(
    request: VolumeRequest | ChapterRequest | ChaptersRequest,
    path: Path,
    volume: int | None,
    chapter: float | None,
    copied_from: Path | None = None,
) -> PlacedFile:
    return PlacedFile(
        download_id=None,
        kind="manga",
        work_id=request.work_id,
        series=request.series,
        author=request.author,
        volume=volume,
        chapter=chapter,
        path=str(path),
        copied_from=None if copied_from is None else str(copied_from),
    )


def same_file(source: Path, target: Path) -> bool:
    """`target` is `source` itself: a file of the libraries already under its name."""
    try:
        return target.exists() and os.path.samefile(source, target)
    except OSError:
        return False


def put(source: Path, target: Path, mode: PlaceMode) -> Outcome:
    """`source` hardlinked (or copied, `mode`) as `target`; `exists` when a file is there.
    Raises NotPlacedError."""
    return lay_file(source, target, mode)


def laid(folder: Path, files: Sequence[PlacedFile], covers: bool) -> Laid:
    return Laid(
        folder=folder,
        files=tuple(files),
        volumes=tuple(sorted({f.volume for f in files if f.volume is not None})),
        present=(),
        cover=series_cover(folder) if covers and files else None,
    )


def place_volume(
    sources: Sequence[str],
    request: VolumeRequest,
    root: Path,
    covers: bool,
    mode: PlaceMode = "hardlink",
) -> HandLaid:
    """One volume of a manga as `<Series> - TXX.<ext>`. Raises NotPlacedError (`exists` when a
    file has that name)."""
    books = [Path(s) for s in sources if Path(s).suffix.lower() in COMIC_EXTENSIONS]
    if not books:
        raise NotPlacedError("no_files")
    folder = root / safe(request.series)
    target = folder / comic_name(request.series, request.volume or 1, books[0].suffix)
    if same_file(books[0], target):
        placed = [shelf_file(request, target, request.volume or 1, None)]
        return HandLaid(laid=laid(folder, placed, covers), used=())
    make_folder(folder)
    outcome = put(books[0], target, mode)
    if outcome == "exists":
        raise NotPlacedError("exists")
    copied = copy_source(books[0], outcome)
    placed = [shelf_file(request, target, request.volume or 1, None, copied)]
    return HandLaid(laid=laid(folder, placed, covers), used=(str(books[0]),))


def place_chapter(
    sources: Sequence[str],
    request: ChapterRequest,
    root: Path,
    covers: bool,
    mode: PlaceMode = "hardlink",
) -> HandLaid:
    """One file of chapters as `<Series> - T23 - Ch. 206` or `<Series> - Ch. 233-236`. Raises
    NotPlacedError."""
    books = [Path(s) for s in sources if Path(s).suffix.lower() in COMIC_EXTENSIONS]
    if not books:
        raise NotPlacedError("no_files")
    folder = root / safe(request.series)
    target = folder / chapter_name(
        request.series, request.volume, request.first, books[0].suffix, request.last
    )
    if same_file(books[0], target):
        placed = [shelf_file(request, target, request.volume, request.first)]
        return HandLaid(laid=laid(folder, placed, covers), used=())
    make_folder(folder)
    outcome = put(books[0], target, mode)
    if outcome == "exists":
        raise NotPlacedError("exists")
    copied = copy_source(books[0], outcome)
    placed = [shelf_file(request, target, request.volume, request.first, copied)]
    return HandLaid(laid=laid(folder, placed, covers), used=(str(books[0]),))


def whole_chapters(first: float, last: float) -> list[float]:
    """The whole chapters of a volume: the `.5` are never awaited."""
    return [float(n) for n in range(math.ceil(first), int(last) + 1)]


def ordered_files(chapters: dict[float, str], first: float, last: float) -> list[str]:
    """The files of the chapters `first` to `last`, in the order of their chapters, once each."""
    files: list[str] = []
    for chapter in sorted(c for c in chapters if first <= c <= last):
        if chapters[chapter] not in files:
            files.append(chapters[chapter])
    return files


def merge_volume(files: Sequence[str], target: Path, info: ComicInfo, replace: bool) -> None:
    """The chapters `files` merged into `target`, its cover their first page; a volume there
    replaced only when `replace`. Raises NotPlacedError."""
    try:
        cover = first_page(Path(files[0]))
    except ArchiveError:
        cover = None
    out = target.with_name(target.stem + ".merging" + target.suffix) if replace else target
    try:
        merge_chapters([Path(f) for f in files], out, info, cover)
    except FileExistsError as exc:
        raise NotPlacedError("exists") from exc
    except ArchiveError as exc:
        raise NotPlacedError("merge_failed") from exc
    if replace:
        out.replace(target)


def loose_files(folder: Path, names: Sequence[str], taken: set[str]) -> dict[float, str]:
    """The chapters loose in `folder` (its CBZ of chapters, `names`), but the files `taken`:
    each chapter and its file."""
    return {
        chapter: path
        for chapter, path in chapter_files(
            str(folder / n)
            for n in names
            if Path(n).suffix.lower() == ".cbz" and chapters_of(Path(n).stem) is not None
        ).items()
        if path not in taken
    }


def loose_chapters(folder: Path, taken: Sequence[str]) -> tuple[float, ...]:
    """The chapters loose in `folder` but in the files `taken`: those `place_chapters` counts
    with a release to make a volume complete."""
    return tuple(sorted(loose_files(folder, names_in(folder), set(taken))))


def place_chapters(
    sources: Sequence[str],
    request: ChaptersRequest,
    root: Path,
    covers: bool,
    mode: PlaceMode = "hardlink",
) -> HandLaid:
    """A release in chapters linked to its volumes. The chapters already loose in the folder of
    the series count with those of the release: a volume complete with them is merged, and
    its loose chapters removed. Raises NotPlacedError."""
    folder = root / safe(request.series)
    names = names_in(folder)
    shelf = content_of(names)
    release = chapter_files(s for s in sources if Path(s).suffix.lower() in COMIC_EXTENSIONS)
    taken = set(release.values())
    loose = loose_files(folder, names, taken)
    make_folder(folder)
    placed: list[PlacedFile] = []
    used: set[str] = set()
    moved: set[str] = set()
    removed: list[str] = []
    for volume in sorted(request.volumes, key=lambda v: v.volume):
        in_range = ordered_files(release, volume.first, volume.last)
        used.update(in_range)
        target = folder / comic_name(request.series, volume.volume, ".cbz")
        if volume.volume in shelf.volumes and not volume.replace:
            continue
        everything = {**loose, **release}
        if all(c in everything for c in whole_chapters(volume.first, volume.last)):
            files = ordered_files(everything, volume.first, volume.last)
            info = ComicInfo(
                series=request.series,
                number=volume.volume,
                writers=tuple(a.strip() for a in request.author.split(",") if a.strip()),
                summary=request.summary,
            )
            merge_volume(files, target, info, volume.replace)
            placed.append(shelf_file(request, target, volume.volume, None))
            moved.update(f for f in files if f in taken)
            gone = [f for f in files if f in loose.values()]
            for path in gone:
                Path(path).unlink(missing_ok=True)
            removed += gone
            continue
        for path in in_range:
            placed += link_chapter(path, request, folder, volume.volume, moved, mode)
    left = tuple(s for s in release.values() if s not in used)
    if request.rest == "place":
        for path in dict.fromkeys(left):
            placed += link_chapter(path, request, folder, None, moved, mode)
        left = ()
    return HandLaid(
        laid=laid(folder, placed, covers),
        used=tuple(sorted(moved)),
        left=tuple(dict.fromkeys(left)),
        removed=tuple(removed),
    )


def link_chapter(
    path: str,
    request: ChaptersRequest,
    folder: Path,
    volume: int | None,
    moved: set[str],
    mode: PlaceMode = "hardlink",
) -> list[PlacedFile]:
    """A file of chapters linked as it is, under its name of the shelf (already there when it is
    that file); none when another file has that name."""
    found = chapters_of(Path(path).stem)
    if found is None:
        return []
    target = folder / chapter_name(
        request.series, volume, found.first, Path(path).suffix, found.last
    )
    if same_file(Path(path), target):
        return [shelf_file(request, target, volume, found.first)]
    outcome = put(Path(path), target, mode)
    if outcome == "exists":
        return []
    moved.add(path)
    return [shelf_file(request, target, volume, found.first, copy_source(Path(path), outcome))]
