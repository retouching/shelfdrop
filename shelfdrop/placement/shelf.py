"""The files of the shelf: what a torrent holds, a hardlink or a copy into a library, a picture
written next to the books. Every write leaves what is there: nothing is replaced."""

import errno
import os
import shutil
import subprocess
from pathlib import Path
from typing import Final

from shelfdrop.placement.comics import natural_key
from shelfdrop.placement.types import Outcome, PlaceMode

# The pictures of a series or a book a library may already hold.
COVER_NAMES: Final = ("cover", "folder")
PDFTOPPM: Final = "pdftoppm"
PDF_SECONDS: Final = 60
# The errors of a hardlink the file system refuses: another file system, no right on the file,
# too many links.
REFUSED: Final = frozenset({errno.EXDEV, errno.EPERM, errno.EACCES, errno.EMLINK})
# The errors of a file system that makes no hardlink at all (the last step of a copy renames).
NO_LINKS: Final = frozenset(
    {errno.EPERM, errno.EMLINK, errno.EOPNOTSUPP, errno.ENOTSUP, errno.ENOSYS}
)
COPY_BYTES: Final = 1024 * 1024


class LinkRefusedError(Exception):
    """The file system refused a hardlink: another file system, or no right on the file."""


class CopyFailedError(Exception):
    """A copy cut before its end (no space left, a read that failed): nothing left at the
    target."""


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


def place_file(source: Path, target: Path, mode: PlaceMode) -> Outcome:
    """`source` put as `target`, the one way every placement takes (`placement.mode`): a
    hardlink (the torrent seeds on, without a second copy), else, a link refused, a copy in
    `hardlink_or_copy`; a copy always in `copy`. `exists` when `target` exists (left as it
    is). Raises LinkRefusedError (`hardlink`), CopyFailedError."""
    if mode != "copy":
        try:
            os.link(source, target)
        except FileExistsError:
            return "exists"
        except OSError as exc:
            if exc.errno not in REFUSED:
                raise
            if mode == "hardlink":
                raise LinkRefusedError(errno.errorcode.get(exc.errno or 0, "OSError")) from exc
        else:
            return "linked"
    return copy_new(source, target)


def copy_new(source: Path, target: Path) -> Outcome:
    """`source` copied to `target` through `<target>.part`, written to the disk, then linked
    to its name (a file there is never replaced; on a file system without hardlinks, renamed
    once the name is checked free): Jellyfin never sees half a file. Raises CopyFailedError,
    the `.part` removed."""
    if target.exists():
        return "exists"
    part = target.with_name(target.name + ".part")
    try:
        with source.open("rb") as read, part.open("wb") as write:
            shutil.copyfileobj(read, write, COPY_BYTES)
            write.flush()
            os.fsync(write.fileno())
        return name_part(part, target)
    except OSError as exc:
        raise CopyFailedError(errno.errorcode.get(exc.errno or 0, type(exc).__name__)) from exc
    finally:
        part.unlink(missing_ok=True)


def name_part(part: Path, target: Path) -> Outcome:
    """The `.part` given its name, never over a file."""
    try:
        os.link(part, target)
    except FileExistsError:
        return "exists"
    except OSError as exc:
        if exc.errno not in NO_LINKS:
            raise
        if target.exists():
            return "exists"
        part.rename(target)
    return "copied"


def moving_mode(mode: PlaceMode) -> PlaceMode:
    """The mode of a file of the libraries or sent from the page, moved (placed, then its old
    name removed): a copy only when the link is refused, never in `hardlink`."""
    return "hardlink" if mode == "hardlink" else "hardlink_or_copy"


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
