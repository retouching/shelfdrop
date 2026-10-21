"""The files sent from the page Manuel (plan section 3, point 6), taken by the worker: moved from
the data directory into the folder of the uploads (`uploads.folder`, on the file system of the
libraries: a file placed from there is linked, then its old name removed), a ZIP opened there;
then each book is a file of Ranger, to link to a work. The moves run in the threadpool."""

import shutil
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Final

from shelfdrop.placement.types import NewItem
from shelfdrop.works.types import Kind

# The kind a file sent most likely is, by its extension (a PDF or an EPUB is a book, a CBZ a
# manga): the page changes it when linking it. A ZIP has none: it is opened.
KINDS: Final[dict[str, Kind]] = {
    ".cbz": "manga",
    ".cbr": "manga",
    ".cb7": "manga",
    ".epub": "ebook",
    ".pdf": "ebook",
    ".mobi": "ebook",
    ".azw3": "ebook",
    ".m4b": "audiobook",
    ".m4a": "audiobook",
    ".mp3": "audiobook",
    ".flac": "audiobook",
    ".opus": "audiobook",
    ".ogg": "audiobook",
    ".aac": "audiobook",
}
# A ZIP sent opens to this many bytes at most.
UNZIPPED_MAX_BYTES: Final = 10 * 1024**3
COPY_BYTES: Final = 16 * 1024 * 1024


class ZipRefusedError(Exception):
    """A ZIP whose entries leave its folder, or open to more than UNZIPPED_MAX_BYTES."""


def move_in(source: Path, folder: Path) -> Path:
    """`source` copied into `folder` through a `.part` (another file system), then removed. A
    copy there already (a round cut before the removal) is kept."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    if not target.exists():
        part = target.with_name(target.name + ".part")
        with source.open("rb") as read, part.open("wb") as write:
            shutil.copyfileobj(read, write, COPY_BYTES)
        part.replace(target)
    source.unlink(missing_ok=True)
    return target


def safe_entry(name: str) -> PurePosixPath | None:
    """The path of a ZIP entry inside its folder; None for a folder, a hidden file, or a path
    that leaves it."""
    path = PurePosixPath(name.replace("\\", "/"))
    if name.endswith("/") or path.is_absolute() or ".." in path.parts:
        return None
    if any(part.startswith(".") or part == "__MACOSX" for part in path.parts):
        return None
    return path


def open_zip(archive: Path) -> list[Path]:
    """The files of `archive`, opened into the folder of its name next to it; the archive
    removed. Raises ZipRefusedError, zipfile.BadZipFile."""
    folder = archive.with_suffix("")
    with zipfile.ZipFile(archive) as opened:
        entries = [(info, safe_entry(info.filename)) for info in opened.infolist()]
        if sum(info.file_size for info, _ in entries) > UNZIPPED_MAX_BYTES:
            raise ZipRefusedError
        found: list[Path] = []
        for info, path in entries:
            if path is None:
                continue
            target = folder.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with opened.open(info) as read, target.open("wb") as write:
                shutil.copyfileobj(read, write, COPY_BYTES)
            found.append(target)
    archive.unlink()
    return sorted(found)


def lay_upload(source: Path, folder: Path) -> list[tuple[str, int]]:
    """The file sent moved into `folder`, a ZIP opened (a ZIP that does not open stays as it
    is); its files and their sizes. Raises OSError (`source` gone)."""
    target = move_in(source, folder)
    files = [target]
    if target.suffix.lower() == ".zip":
        try:
            files = open_zip(target)
        except (zipfile.BadZipFile, ZipRefusedError):
            shutil.rmtree(target.with_suffix(""), ignore_errors=True)
    return [(str(f), f.stat().st_size) for f in files]


def upload_items(name: str, files: Sequence[tuple[str, int]]) -> list[NewItem]:
    """The files of Ranger of a file sent: each book one, the MP3 tracks of one folder one (an
    audiobook to merge); a file sent with no book one, of no kind. Pure."""

    def item(label: str, path: str, group: Sequence[tuple[str, int]], kind: Kind | None) -> NewItem:
        return NewItem(
            origin="upload",
            download_id=None,
            kind=kind,
            name=label,
            path=path,
            files=tuple(p for p, _ in group),
            size=sum(size for _, size in group),
            state="unlinked",
            reason="upload",
        )

    books = [(p, s) for p, s in files if PurePosixPath(p).suffix.lower() in KINDS]
    if not books:
        return [item(name, files[0][0], files, None)] if files else []
    found: list[NewItem] = []
    tracks: dict[str, list[tuple[str, int]]] = {}
    for path, size in books:
        if PurePosixPath(path).suffix.lower() == ".mp3":
            tracks.setdefault(str(PurePosixPath(path).parent), []).append((path, size))
        else:
            found.append(
                item(
                    PurePosixPath(path).name,
                    path,
                    [(path, size)],
                    KINDS[PurePosixPath(path).suffix.lower()],
                )
            )
    for folder, group in tracks.items():
        if len(group) == 1:
            found.append(item(PurePosixPath(group[0][0]).name, group[0][0], group, "audiobook"))
        else:
            found.append(item(PurePosixPath(folder).name, folder, group, "audiobook"))
    return found


def remove_upload(paths: Sequence[str], folder: Path) -> None:
    """The files of a file sent left in Ranger too long, and the folders of `folder` they
    leave empty."""
    for path in paths:
        target = Path(path)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
    remove_empty(folder)


def remove_empty(folder: Path) -> None:
    """The empty folders under `folder` (an upload placed leaves its own)."""
    if not folder.is_dir():
        return
    for path in sorted(folder.rglob("*"), key=lambda p: -len(p.parts)):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
