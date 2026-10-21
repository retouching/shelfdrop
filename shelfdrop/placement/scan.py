"""The scan of the libraries for the files misplaced (plan section 3, points 4 bis and 5): a file
at the root of a library, a file out of the names of the shelf, a folder of chapters of a manga
(merged into volumes from Ranger), a folder of MP3 tracks not merged into one M4B. What the
placement put there itself is left aside. Runs in the threadpool: file system alone."""

import re
from collections.abc import Collection
from pathlib import Path
from typing import Final

from shelfdrop.placement.comics import natural_key
from shelfdrop.placement.existing import content_of
from shelfdrop.placement.items import chapter_numbers
from shelfdrop.placement.naming import (
    AUDIO_EXTENSIONS,
    COMIC_EXTENSIONS,
    EBOOK_EXTENSIONS,
    comic_name,
    file_volume,
)
from shelfdrop.placement.types import ItemState, Misplaced, NewItem
from shelfdrop.releases.guess import chapters_of
from shelfdrop.works.types import Kind

# The folder of a volume of a book: '01 - Le Vaisseau magique'.
VOLUME_FOLDER: Final = re.compile(r"^\d{2,3} - .+")
# The files of a library found at most in one scan, by library.
LIMIT: Final = 1000
BOOKS: Final[dict[Kind, tuple[str, ...]]] = {
    "manga": COMIC_EXTENSIONS,
    "ebook": EBOOK_EXTENSIONS,
    "audiobook": AUDIO_EXTENSIONS,
}


def is_hidden(path: Path, root: Path) -> bool:
    return any(part.startswith(".") for part in path.relative_to(root).parts) or (
        path.name.endswith(".part")
    )


def size_of(paths: Collection[Path]) -> int:
    total = 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def found(
    kind: Kind,
    paths: list[Path],
    state: ItemState,
    reason: Misplaced,
    *,
    path: Path | None = None,
    series: str = "",
    author: str = "",
    existing: tuple[int, ...] = (),
) -> NewItem:
    where = path if path is not None else paths[0]
    files = tuple(str(p) for p in sorted(paths, key=lambda p: natural_key(p.name)))
    return NewItem(
        origin="library",
        download_id=None,
        kind=kind,
        name=where.name,
        path=str(where),
        files=files,
        size=size_of(paths),
        state=state,
        reason=reason,
        chapters=chapter_numbers(files) if state == "chapters" else (),
        series=series,
        existing=existing,
        author=author,
    )


def scan_comics(root: Path, placed: Collection[str]) -> list[NewItem]:
    """A manga: a file at the root; in the folder of a series, a volume out of
    `<Series> - TXX`, a file in a folder of it; its chapters not placed by shelfdrop, one item
    to link to volumes."""
    items: list[NewItem] = []
    for entry in sorted(root.iterdir()):
        if is_hidden(entry, root):
            continue
        if entry.is_file():
            if entry.suffix.lower() in COMIC_EXTENSIONS:
                items.append(found("manga", [entry], "misplaced", "root"))
            continue
        if not entry.is_dir():
            continue
        files = [
            p
            for p in entry.rglob("*")
            if p.is_file() and p.suffix.lower() in COMIC_EXTENSIONS and not is_hidden(p, root)
        ]
        direct = [p for p in files if p.parent == entry]
        content = content_of(p.name for p in direct)
        existing = tuple(sorted(content.volumes))
        loose: list[Path] = []
        for path in files:
            if str(path) in placed:
                continue
            if path.parent != entry:
                items.append(found("manga", [path], "misplaced", "naming", series=entry.name))
            elif chapters_of(path.stem) is not None:
                loose.append(path)
            else:
                volume = file_volume(path.stem)
                if volume is None or path.name != comic_name(entry.name, volume, path.suffix):
                    items.append(found("manga", [path], "misplaced", "naming", series=entry.name))
        if loose:
            items.append(
                found(
                    "manga",
                    loose,
                    "chapters",
                    "chapters",
                    path=entry,
                    series=entry.name,
                    existing=existing,
                )
            )
    return items


def scan_books(kind: Kind, root: Path, placed: Collection[str], merge_mp3: bool) -> list[NewItem]:
    """A book or an audiobook: a file at the root, a file out of
    `<Author>/<Series>/<NN - Title>/`; the MP3 tracks of a folder without an M4B, one item to
    merge."""
    items: list[NewItem] = []
    folders: dict[Path, list[Path]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or is_hidden(path, root):
            continue
        if path.suffix.lower() not in BOOKS[kind] or str(path) in placed:
            continue
        parts = path.relative_to(root).parts
        if kind == "audiobook" and path.suffix.lower() == ".mp3" and len(parts) > 1:
            folders.setdefault(path.parent, []).append(path)
            continue
        if len(parts) == 1:
            items.append(found(kind, [path], "misplaced", "root"))
        elif len(parts) != 4 or not VOLUME_FOLDER.match(parts[2]):
            items.append(found(kind, [path], "misplaced", "naming"))
    for folder, tracks in folders.items():
        parts = folder.relative_to(root).parts
        merged = any(p.suffix.lower() in (".m4b", ".m4a") for p in folder.iterdir() if p.is_file())
        author = parts[0] if len(parts) >= 2 else ""
        series = parts[1] if len(parts) >= 2 else folder.name
        if len(tracks) > 1 and merge_mp3 and not merged:
            items.append(
                found(
                    kind,
                    tracks,
                    "misplaced",
                    "tracks",
                    path=folder,
                    series=series,
                    author=author,
                )
            )
        elif len(parts) != 3 or not VOLUME_FOLDER.match(parts[2]):
            items += [found(kind, [t], "misplaced", "naming") for t in tracks]
    return items


def scan_library(kind: Kind, root: Path, placed: Collection[str], merge_mp3: bool) -> list[NewItem]:
    """The files misplaced of the library of `kind` at `root` (none when it does not exist),
    `LIMIT` at most; `placed`, the paths the placement put there."""
    if not root.is_dir():
        return []
    items = (
        scan_comics(root, placed) if kind == "manga" else scan_books(kind, root, placed, merge_mp3)
    )
    return items[:LIMIT]
