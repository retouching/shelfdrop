"""The archives of comics: the pages of a CBZ in their order, its first page (the cover of a
series), and the chapters of a volume merged into one CBZ with its cover and its
`ComicInfo.xml` (plan section 3, point 4 bis)."""

import re
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Final
from xml.sax.saxutils import escape

from shelfdrop.placement.naming import IMAGE_EXTENSIONS
from shelfdrop.placement.types import ComicInfo

# What a page of an archive is not.
SKIPPED: Final = ("__MACOSX/", ".")
FRONT: Final = ' Type="FrontCover"'


class ArchiveError(Exception):
    """An archive that cannot be read, or holds no page."""


def natural_key(name: str) -> list[int | str]:
    """'p2' before 'p10'."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def is_page(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        path.suffix.lower() in IMAGE_EXTENSIONS
        and not name.startswith(SKIPPED[0])
        and not path.name.startswith(SKIPPED[1])
    )


def pages_of(archive: zipfile.ZipFile) -> list[str]:
    """The pages of an archive in their natural order."""
    return sorted((n for n in archive.namelist() if is_page(n)), key=natural_key)


def first_page(path: Path) -> tuple[bytes, str]:
    """The first page of a CBZ (a zip) and its extension. Raises ArchiveError."""
    try:
        with zipfile.ZipFile(path) as archive:
            pages = pages_of(archive)
            if not pages:
                raise ArchiveError("no page")
            return archive.read(pages[0]), PurePosixPath(pages[0]).suffix.lower()
    except (OSError, zipfile.BadZipFile) as exc:
        raise ArchiveError(type(exc).__name__) from exc


def comic_info_xml(info: ComicInfo, pages: int, cover: bool) -> str:
    """The `ComicInfo.xml` of a volume: its series, its number, its writers, its summary, its
    pages, the first one declared its cover."""
    fields = [
        ("Series", info.series),
        ("Number", str(info.number)),
        ("Title", info.title),
        ("Writer", ", ".join(info.writers)),
        ("Summary", info.summary),
        ("PageCount", str(pages)),
        ("Manga", "Yes"),
    ]
    body = "".join(f"  <{name}>{escape(value)}</{name}>\n" for name, value in fields if value)
    listed = "".join(
        f'    <Page Image="{index}"{FRONT if cover and index == 0 else ""} />\n'
        for index in range(pages)
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        f"{body}  <Pages>\n{listed}  </Pages>\n</ComicInfo>\n"
    )


def merge_chapters(
    chapters: Sequence[Path], out: Path, info: ComicInfo, cover: tuple[bytes, str] | None
) -> int:
    """One CBZ of `chapters` (in their order): `cover` first when given, then the pages of each
    chapter in order, numbered again from 1; written into `<out>.part`, renamed once whole. A
    file already at `out` is never replaced (FileExistsError). Raises ArchiveError. Returns the
    pages written."""
    if out.exists():
        raise FileExistsError(out)
    part = out.with_name(out.name + ".part")
    written = 0
    try:
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_STORED) as target:
            if cover is not None:
                data, extension = cover
                target.writestr(f"{written:04d}{extension}", data)
                written += 1
            for chapter in chapters:
                with zipfile.ZipFile(chapter) as source:
                    for name in pages_of(source):
                        extension = PurePosixPath(name).suffix.lower()
                        target.writestr(f"{written:04d}{extension}", source.read(name))
                        written += 1
            if written == 0:
                raise ArchiveError("no page")
            target.writestr("ComicInfo.xml", comic_info_xml(info, written, cover is not None))
        if out.exists():
            raise FileExistsError(out)
        part.rename(out)
    except (OSError, zipfile.BadZipFile) as exc:
        part.unlink(missing_ok=True)
        if isinstance(exc, FileExistsError):
            raise
        raise ArchiveError(type(exc).__name__) from exc
    except ArchiveError:
        part.unlink(missing_ok=True)
        raise
    return written
