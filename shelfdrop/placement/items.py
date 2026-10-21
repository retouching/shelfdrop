"""The files of Ranger a download makes (plan section 3, point 5): a release in chapters is one,
to link to its volumes; each book of another release is one, the tracks of one folder of an
audiobook one. Pure: the caller lists the torrent."""

from collections.abc import Iterable, Sequence
from pathlib import PurePath

from shelfdrop.downloads.types import Download
from shelfdrop.placement.existing import is_chapters_release
from shelfdrop.placement.naming import AUDIO_EXTENSIONS, COMIC_EXTENSIONS, EBOOK_EXTENSIONS
from shelfdrop.placement.types import ItemState, NewItem
from shelfdrop.releases.guess import chapters_of

# The extensions of the books of each kind.
BOOKS = {"manga": COMIC_EXTENSIONS, "ebook": EBOOK_EXTENSIONS, "audiobook": AUDIO_EXTENSIONS}


def chapter_numbers(paths: Iterable[str]) -> tuple[float, ...]:
    """Every chapter the names of `paths` hold, in order: 'Ch. 233-236' gives 233 to 236."""
    found: set[float] = set()
    for path in paths:
        chapters = chapters_of(PurePath(path).stem)
        if chapters is None:
            continue
        found.add(chapters.first)
        last = chapters.last if chapters.last is not None else chapters.first
        found.update(float(n) for n in range(int(chapters.first) + 1, int(last) + 1))
        if last != int(last):
            found.add(last)
    return tuple(sorted(found))


def chapter_files(paths: Iterable[str]) -> dict[float, str]:
    """Each chapter of `paths` and the file that holds it (the first one for a duplicate)."""
    found: dict[float, str] = {}
    for path in paths:
        for chapter in chapter_numbers([path]):
            found.setdefault(chapter, path)
    return found


def items_of(
    download: Download,
    content: str,
    files: Sequence[tuple[str, int]],
    existing: Sequence[int],
    loose: Sequence[float] = (),
) -> list[NewItem]:
    """The files of Ranger of `download`: `files`, the paths of its torrent and their sizes;
    `existing`, the volumes of its series on the shelf; `loose`, the chapters loose there,
    given to a release in chapters."""
    reason = download.unplaced or "manual"
    known = (
        download.volumes.last - download.volumes.first + 1
        if download.volumes.kind == "range"
        and download.volumes.first is not None
        and download.volumes.last is not None
        else None
    )

    def item(
        name: str, path: str, group: Sequence[tuple[str, int]], state: ItemState = "unlinked"
    ) -> NewItem:
        paths = tuple(p for p, _ in group)
        return NewItem(
            origin="download",
            download_id=download.id,
            kind=download.kind,
            name=name,
            path=path,
            files=paths,
            size=sum(size for _, size in group) or (download.size if not group else 0),
            state=state,
            reason=reason,
            chapters=chapter_numbers(paths) if state == "chapters" else (),
            series=download.series or download.work_name,
            existing=tuple(sorted(existing)),
            work_id=download.work_id,
            author=download.author,
            loose=tuple(loose) if state == "chapters" else (),
        )

    books = [f for f in files if PurePath(f[0]).suffix.lower() in BOOKS[download.kind]]
    if not books:
        return [item(download.title, content, files)]
    if download.kind == "manga" and is_chapters_release([p for p, _ in books], known):
        return [item(download.title, content, books, "chapters")]
    if download.kind != "audiobook":
        return [item(PurePath(p).name, p, [(p, size)]) for p, size in books]
    folders: dict[str, list[tuple[str, int]]] = {}
    for path, size in books:
        folders.setdefault(str(PurePath(path).parent), []).append((path, size))
    found: list[NewItem] = []
    for folder, tracks in folders.items():
        if len(tracks) == 1:
            path = tracks[0][0]
            found.append(item(PurePath(path).name, path, tracks))
        else:
            name = download.title if folder == content else PurePath(folder).name
            found.append(item(name, folder, tracks))
    return found
