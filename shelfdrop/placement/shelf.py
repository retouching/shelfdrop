"""The files of the shelf: what a torrent holds, a hardlink into a library, a picture written
next to the books. Every write leaves what is there: nothing is replaced."""

import errno
import os
import shutil
import subprocess
from pathlib import Path
from typing import Final

from shelfdrop.placement.comics import natural_key

# The pictures of a series or a book a library may already hold.
COVER_NAMES: Final = ("cover", "folder")
PDFTOPPM: Final = "pdftoppm"
PDF_SECONDS: Final = 60


class LinkRefusedError(Exception):
    """The file system refused a hardlink: another file system, or no right on the file."""


def files_of(content: Path) -> list[Path]:
    """The files of a torrent: its file, or every file of its folder, in their natural order."""
    if content.is_file():
        return [content]
    if not content.is_dir():
        return []
    found = [p for p in content.rglob("*") if p.is_file() and not p.name.startswith(".")]
    return sorted(found, key=lambda p: natural_key(str(p.relative_to(content))))


def names_in(folder: Path) -> list[str]:
    """The names of the files of `folder`; none when it does not exist."""
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_file())


def make_folder(folder: Path) -> None:
    """The folder and its parents, group-writable (the umask of the worker)."""
    folder.mkdir(parents=True, exist_ok=True)


def link(source: Path, target: Path) -> bool:
    """A hardlink `target` of `source`: the torrent seeds on, without a second copy. False when
    `target` exists (left as it is). Raises LinkRefusedError."""
    try:
        os.link(source, target)
    except FileExistsError:
        return False
    except OSError as exc:
        if exc.errno in (errno.EXDEV, errno.EPERM, errno.EACCES, errno.EMLINK):
            raise LinkRefusedError(errno.errorcode.get(exc.errno or 0, "OSError")) from exc
        raise
    return True


def rename_new(source: Path, target: Path) -> bool:
    """`source` renamed `target` in the same library, never over a file: a hardlink `target`,
    then `source` removed. False when `target` exists (both left as they are). Raises
    LinkRefusedError."""
    if source == target:
        return True
    if not link(source, target):
        return False
    source.unlink()
    return True


def write_new(target: Path, data: bytes) -> bool:
    """`data` written to `target` through a `.part`; False when `target` exists."""
    if target.exists():
        return False
    part = target.with_name(target.name + ".part")
    part.write_bytes(data)
    try:
        os.link(part, target)
    except FileExistsError:
        return False
    finally:
        part.unlink(missing_ok=True)
    return True


def replace_with(target: Path, data: bytes) -> None:
    """`data` written to `target` through a `.part`, the file there replaced: a `cover.jpg`
    chosen on the page."""
    part = target.with_name(target.name + ".part")
    part.write_bytes(data)
    part.replace(target)


def cover_in(folder: Path) -> Path | None:
    """The picture of a folder: `cover.*` or `folder.*`."""
    if not folder.is_dir():
        return None
    for path in sorted(folder.iterdir()):
        if path.stem.lower() in COVER_NAMES and path.suffix.lower() in (".jpg", ".jpeg", ".png"):
            return path
    return None


def pdf_cover(pdf: Path) -> bool:
    """`<volume>.jpg` next to a PDF, its first page (Jellyfin reads no cover in a PDF), when
    poppler is there and the picture is not."""
    target = pdf.with_suffix(".jpg")
    tool = shutil.which(PDFTOPPM)
    if tool is None or target.exists():
        return False
    command = [tool, "-jpeg", "-r", "100", "-f", "1", "-l", "1", "-singlefile"]
    try:
        result = subprocess.run(  # noqa: S603  # a fixed tool on a file of the shelf, no shell
            [*command, str(pdf), str(target.with_suffix(""))],
            capture_output=True,
            timeout=PDF_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and target.is_file()


def remove_links(paths: list[Path]) -> None:
    """The hardlinks of the shelf merged into another file: the torrent keeps its own."""
    for path in paths:
        path.unlink(missing_ok=True)
