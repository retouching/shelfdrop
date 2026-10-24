"""Where the files of a download go on the shelf, and their hardlinks (plan section 3, points 4
and 4 bis; the scripts `library_place.py`, `comics_rename.py`, `comics_cover.py` and
`books_rename.py` of the user): what the shelf already holds is compared first, and left as it
is. Runs in the threadpool: file system alone."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from shelfdrop.placement.comics import ArchiveError, first_page
from shelfdrop.placement.existing import content_of, is_chapters_release, split_volumes
from shelfdrop.placement.naming import (
    AUDIO_EXTENSIONS,
    COMIC_EXTENSIONS,
    EBOOK_EXTENSIONS,
    IMAGE_EXTENSIONS,
    book_folder,
    book_name,
    comic_name,
    file_volume,
    safe,
    stated_volume,
    volume_title,
)
from shelfdrop.placement.shelf import (
    LinkRefusedError,
    cover_in,
    link,
    make_folder,
    names_in,
    pdf_cover,
    write_new,
)
from shelfdrop.placement.types import PlacedFile, Unplaced
from shelfdrop.releases.types import Volumes
from shelfdrop.works.types import Kind


class NotPlacedError(Exception):
    """A download the placement leaves to Ranger; `placed` holds what it put on the shelf
    before."""

    def __init__(self, reason: Unplaced, placed: Sequence[PlacedFile] = ()) -> None:
        super().__init__(reason)
        self.reason: Unplaced = reason
        self.placed = tuple(placed)


@dataclass(frozen=True, kw_only=True)
class Order:
    """What a download places: its kind, its work, its series, its author and its volumes, as
    the page gave them."""

    download_id: int | None
    kind: Kind
    work_id: str | None
    series: str
    author: str
    release: str
    volumes: Volumes
    title: str = ""
    """The title of the volume, given by Ranger; read in the name of the release without it."""


@dataclass(frozen=True, kw_only=True)
class Laid:
    """The files a download put on the shelf, the volumes already there, a cover, and the
    files of the torrent whose volume it could not read (left to Ranger)."""

    folder: Path
    files: tuple[PlacedFile, ...]
    volumes: tuple[int, ...]
    present: tuple[int, ...]
    cover: bytes | None
    unknown: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class AudioVolume:
    """The tracks of one volume of an audiobook, linked into its folder, to merge."""

    volume: int
    folder: Path
    title: str
    tracks: tuple[Path, ...]
    cover: Path | None
    target: Path


def known_volumes(volumes: Volumes) -> int | None:
    if volumes.kind == "range" and volumes.first is not None and volumes.last is not None:
        return volumes.last - volumes.first + 1
    return None


def placed_file(order: Order, path: Path, volume: int | None) -> PlacedFile:
    return PlacedFile(
        download_id=order.download_id,
        kind=order.kind,
        work_id=order.work_id,
        series=order.series,
        author=order.author,
        volume=volume,
        chapter=None,
        path=str(path),
    )


def comic_volumes(order: Order, books: Sequence[Path]) -> tuple[list[tuple[str, int]], list[str]]:
    """Each book and its volume: read in its name; a release of one file without a number is
    its volume (or T01, as `comics_rename.py` did). The books whose volume it cannot read come
    second."""
    found: list[tuple[str, int]] = []
    unknown: list[str] = []
    for book in books:
        volume = file_volume(book.stem)
        if volume is None and len(books) == 1:
            volume = order.volumes.first if order.volumes.kind == "single" else 1
        if volume is None:
            unknown.append(str(book))
            continue
        found.append((str(book), volume or 1))
    return found, unknown


def place_comics(order: Order, files: Sequence[Path], root: Path, covers: bool) -> Laid:
    """The volumes of a manga as `<Series> - TXX.<ext>` in the folder of its series, those the
    shelf has left aside; the cover of the series (`cover.<ext>`, the first page of its first
    volume) when it has none; a picture of each PDF. The books whose volume it cannot read are
    left (`unknown`), the others placed. Raises NotPlacedError (`no_volume` when it can read
    none)."""
    books = [f for f in files if f.suffix.lower() in COMIC_EXTENSIONS]
    if not books:
        raise NotPlacedError("no_files")
    if is_chapters_release([b.name for b in books], known_volumes(order.volumes)):
        raise NotPlacedError("chapters")
    volumes, unknown = comic_volumes(order, books)
    if not volumes:
        raise NotPlacedError("no_volume")
    folder = root / safe(order.series)
    split = split_volumes(volumes, content_of(names_in(folder)))
    make_folder(folder)
    placed: list[PlacedFile] = []
    present = list(split.present)
    for source, volume in split.added:
        target = folder / comic_name(order.series, volume, Path(source).suffix)
        try:
            if not link(Path(source), target):
                present.append(volume)
                continue
        except LinkRefusedError as exc:
            raise NotPlacedError("link_refused", placed) from exc
        placed.append(placed_file(order, target, volume))
        if target.suffix.lower() == ".pdf":
            pdf_cover(target)
    cover = series_cover(folder) if covers else None
    return Laid(
        folder=folder,
        files=tuple(placed),
        volumes=tuple(sorted(p.volume for p in placed if p.volume is not None)),
        present=tuple(sorted(set(present))),
        cover=cover,
        unknown=tuple(unknown),
    )


def series_cover(folder: Path) -> bytes | None:
    """The cover of a series: its `cover.*` or `folder.*`, or else the first page of its first
    volume, written as `cover.<ext>`."""
    found = cover_in(folder)
    if found is not None:
        return found.read_bytes()
    volumes = sorted(
        (p for p in folder.iterdir() if p.suffix.lower() in (".cbz", ".zip")),
        key=lambda p: (file_volume(p.stem) or 9999, p.name),
    )
    for volume in volumes:
        try:
            data, extension = first_page(volume)
        except ArchiveError:
            continue
        write_new(folder / f"cover{'.jpg' if extension == '.jpeg' else extension}", data)
        return data
    return None


def book_volumes(order: Order, books: Sequence[Path]) -> tuple[dict[int, list[Path]], list[str]]:
    """The files of each volume of a book: all of them for one volume; in a pack, the volume
    its folder or its name states; one book without one is volume 1. The files whose volume it
    cannot read come second."""
    if order.volumes.kind == "single" and order.volumes.first is not None:
        return {order.volumes.first: list(books)}, []
    found: dict[int, list[Path]] = {}
    unknown: list[str] = []
    folders = {b.parent for b in books}
    for book in books:
        volume = stated_volume(book.parent.name) or stated_volume(book.stem)
        if volume is None and len(folders) == 1 and order.volumes.kind != "range":
            volume = 1
        if volume is None:
            unknown.append(str(book))
            continue
        found.setdefault(volume, []).append(book)
    return found, unknown


def title_of(order: Order, volume: int, books: Sequence[Path]) -> str:
    if order.title.strip():
        return order.title.strip()
    if order.volumes.kind == "single":
        return volume_title(order.release, volume, order.series)
    return volume_title(books[0].parent.name, volume, order.series)


def place_books(order: Order, files: Sequence[Path], root: Path) -> Laid:
    """The volumes of a book as `<Author>/<Series>/<NN - Title>/<Series> - TNN - <Title>.<ext>`
    (one file a format); a volume whose folder already holds a book is left. The files whose
    volume it cannot read are left (`unknown`), the others placed. Raises NotPlacedError
    (`no_volume` when it can read none)."""
    books = [f for f in files if f.suffix.lower() in EBOOK_EXTENSIONS]
    if not books:
        raise NotPlacedError("no_files")
    if not order.author.strip():
        raise NotPlacedError("unknown_author")
    volumes, unknown = book_volumes(order, books)
    if not volumes:
        raise NotPlacedError("no_volume")
    placed: list[PlacedFile] = []
    present: list[int] = []
    folder = root
    for volume, group in sorted(volumes.items()):
        title = title_of(order, volume, group)
        folder = root.joinpath(*book_folder(order.author, order.series, volume, title))
        if any(Path(n).suffix.lower() in EBOOK_EXTENSIONS for n in names_in(folder)):
            present.append(volume)
            continue
        make_folder(folder)
        taken: set[str] = set()
        for book in group:
            extension = book.suffix.lower()
            if extension in taken:
                continue
            taken.add(extension)
            target = folder / book_name(order.series, volume, title, extension, None)
            try:
                if link(book, target):
                    placed.append(placed_file(order, target, volume))
            except LinkRefusedError as exc:
                raise NotPlacedError("link_refused", placed) from exc
    return Laid(
        folder=folder.parent if placed or present else root,
        files=tuple(placed),
        volumes=tuple(sorted({p.volume for p in placed if p.volume is not None})),
        present=tuple(present),
        cover=None,
        unknown=tuple(unknown),
    )


def torrent_picture(files: Sequence[Path]) -> Path | None:
    """The picture of a torrent of an audiobook: `cover.*` or `folder.*`, or else its first
    picture."""
    pictures = [f for f in files if f.suffix.lower() in IMAGE_EXTENSIONS]
    named = [p for p in pictures if p.stem.lower() in ("cover", "folder")]
    found = named or pictures
    return found[0] if found else None


def lay_audio(
    order: Order, files: Sequence[Path], root: Path, merge: bool
) -> tuple[Laid, list[AudioVolume]]:
    """The volumes of an audiobook: one M4B linked as `<Series> - TNN - <Title>.m4b`; MP3
    tracks linked as `... - 001.mp3` in their order, to merge (`merge`) into one M4B; the
    picture of the torrent as `cover.<ext>`. A volume whose folder already holds an M4B, or
    tracks, is left. Raises NotPlacedError (`no_volume` as soon as one track has no volume: the
    tracks of an audiobook go by folder, not one by one)."""
    tracks = [f for f in files if f.suffix.lower() in AUDIO_EXTENSIONS]
    if not tracks:
        raise NotPlacedError("no_files")
    if not order.author.strip():
        raise NotPlacedError("unknown_author")
    placed: list[PlacedFile] = []
    present: list[int] = []
    merges: list[AudioVolume] = []
    picture = torrent_picture(files)
    folder = root
    volumes, unknown = book_volumes(order, tracks)
    if unknown:
        raise NotPlacedError("no_volume")
    for volume, group in sorted(volumes.items()):
        title = title_of(order, volume, group)
        folder = root.joinpath(*book_folder(order.author, order.series, volume, title))
        if any(Path(n).suffix.lower() in AUDIO_EXTENSIONS for n in names_in(folder)):
            present.append(volume)
            continue
        make_folder(folder)
        if picture is not None:
            link_or_skip(picture, folder / f"cover{picture.suffix.lower()}")
        single = [t for t in group if t.suffix.lower() in (".m4b", ".m4a")]
        try:
            if single:
                target = folder / book_name(order.series, volume, title, ".m4b", None)
                if link(single[0], target):
                    placed.append(placed_file(order, target, volume))
                continue
            linked: list[Path] = []
            for index, track in enumerate(group, 1):
                target = folder / book_name(
                    order.series, volume, title, track.suffix, index if len(group) > 1 else None
                )
                if link(track, target):
                    linked.append(target)
        except LinkRefusedError as exc:
            raise NotPlacedError("link_refused", placed) from exc
        mp3 = [t for t in linked if t.suffix.lower() == ".mp3"]
        if merge and len(mp3) >= 2:
            merges.append(
                AudioVolume(
                    volume=volume,
                    folder=folder,
                    title=title,
                    tracks=tuple(mp3),
                    cover=cover_in(folder),
                    target=folder / book_name(order.series, volume, title, ".m4b", None),
                )
            )
        else:
            placed += [placed_file(order, t, volume) for t in linked]
    return (
        Laid(
            folder=folder.parent if placed or present or merges else root,
            files=tuple(placed),
            volumes=tuple(sorted({p.volume for p in placed if p.volume is not None})),
            present=tuple(present),
            cover=None,
        ),
        merges,
    )


def link_or_skip(source: Path, target: Path) -> None:
    """A picture of the torrent next to the book; a refused link copies it (it is small)."""
    try:
        link(source, target)
    except LinkRefusedError:
        write_new(target, source.read_bytes())
