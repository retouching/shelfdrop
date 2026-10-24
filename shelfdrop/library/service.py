"""LibraryService: the page Jellyfin. The series of the libraries of books of Jellyfin, their
volumes and their files, what the sources propose for them, their fields and their image set
and locked, the scans; the `cover.jpg` of a series asked of the placement worker (the API never
writes in the libraries, ADR 0016)."""

import logging
from collections.abc import Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass
from functools import wraps
from pathlib import PurePosixPath
from typing import Any, Final, Protocol

import anyio
import anyio.to_thread

from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.clients.types import JellyfinItem, JellyfinLibrary
from shelfdrop.library.exceptions import (
    AdoptionRefusedError,
    ImageRefusedError,
    LibraryUnavailableError,
    SeriesNotFoundError,
    VolumeNotFoundError,
)
from shelfdrop.library.types import (
    AdoptionChoice,
    AdoptionFile,
    AdoptionResult,
    ImageChoice,
    ItemImage,
    LibrarySeries,
    LibraryVolume,
    LinkImage,
    NumberOrigin,
    ScanOrder,
    SentImage,
    SeriesAdoption,
    SeriesChange,
    SeriesProposals,
    SeriesVolumes,
    SourceCover,
    SourceSummary,
    VolumeChange,
    VolumeFile,
    VolumeImage,
)
from shelfdrop.placement.naming import adopted_name, file_chapter, file_volume
from shelfdrop.placement.paths import library_of, to_jellyfin, to_local
from shelfdrop.placement.repository import PlacementRepository
from shelfdrop.placement.types import AdoptOrder, PlacedFile, SeriesLink
from shelfdrop.utils.pictures import picture_of
from shelfdrop.works.exceptions import (
    NoSourceAnsweredError,
    QueryTooShortError,
    WorkNotFoundError,
)
from shelfdrop.works.types import Clock, Kind, Work, WorkSearch

logger = logging.getLogger(__name__)

VOLUME_TYPES: Final = ("Book", "AudioBook")
ITEM_TYPES: Final = (*VOLUME_TYPES, "Folder")
# An image sent or read over this size is refused.
IMAGE_MAX_BYTES: Final = 5 * 1024 * 1024
# The width of the image of a volume read to be set elsewhere.
IMAGE_WIDTH: Final = 2000
# The volumes whose image the page proposes, at most.
VOLUME_PROPOSALS: Final = 8
# The fields of an item a change locks, when asked (`MetadataField`, F30).
LOCKED: Final = ("Name", "Overview", "Genres", "Cast")
# The sizes of the files of a series read at once.
SIZE_READS: Final = 4
EXTENSIONS: Final[Mapping[Kind, str]] = {"manga": "CBZ", "ebook": "EPUB", "audiobook": "M4B"}


class LibrarySettings(Protocol):
    async def jellyfin(self) -> tuple[str | None, str | None]: ...

    async def libraries(self) -> dict[Kind, str]: ...


class WorkFinder(Protocol):
    """The work search, under the name of a series, and a work it found by its id."""

    async def search(self, query: str, kind: Kind) -> WorkSearch: ...

    async def read_work(self, work_id: str) -> Work: ...


class ImageReader(Protocol):
    """An image at an address (5 MB at most), None when it is not one."""

    async def image(self, url: str) -> bytes | None: ...


type PlacementRepositoryFactory = Callable[[], PlacementRepository]


@dataclass(frozen=True, kw_only=True)
class Shelf:
    """The library of Jellyfin of a kind, and its folder there."""

    kind: Kind
    item_id: str
    library: JellyfinLibrary
    location: str


def series_folder(path: str, location: str, kind: Kind) -> str | None:
    """The folder of the series of a volume at `path` (as Jellyfin sees it): the first folder of
    the library for a manga (`<Series>/`), the second for a book (`<Author>/<Series>/`), else
    its first; None for a file at the root of the library."""
    try:
        folders = PurePosixPath(path).relative_to(location).parts[:-1]
    except ValueError:
        return None
    if not folders:
        return None
    depth = 2 if kind != "manga" and len(folders) >= 2 else 1
    return str(PurePosixPath(location).joinpath(*folders[:depth]))


def volume_label(volume: JellyfinItem, kind: Kind) -> str:
    number = volume.index_number
    name = f"Tome {number}" if number is not None else volume.name
    return f"{name} \u00b7 {EXTENSIONS[kind]}"


def changed_item(
    body: dict[str, Any], change: SeriesChange, *, fields: bool, summary: bool
) -> dict[str, Any]:
    """The item read, with the fields of the change (`fields`) and its summary (`summary`) set,
    and locked when asked."""
    item = dict(body)
    locked = set(item.get("LockedFields") or [])
    if fields:
        item["Name"] = change.name
        item["OriginalTitle"] = change.original_title
        item["ProductionYear"] = change.year
        item["Genres"] = list(change.genres)
        others = [
            p for p in item.get("People") or [] if isinstance(p, dict) and p.get("Type") != "Author"
        ]
        item["People"] = [
            *({"Name": a, "Type": "Author", "Role": ""} for a in change.authors),
            *others,
        ]
        if change.lock:
            locked |= {"Name", "Genres", "Cast"}
    if summary:
        item["Overview"] = change.summary
        if change.lock:
            locked |= {"Overview"}
    item["LockedFields"] = sorted(locked)
    return item


def number_of(volume: JellyfinItem) -> int | None:
    """Its number in Jellyfin, else in the name of its file."""
    if volume.index_number is not None:
        return volume.index_number
    return file_volume(PurePosixPath(volume.path).stem)


def missing_numbers(numbers: Sequence[int | None]) -> tuple[int, ...]:
    """The numbers between 1 and the highest given that none of them is."""
    held = {n for n in numbers if n is not None and n > 0}
    return tuple(n for n in range(1, max(held, default=0) + 1) if n not in held)


def changed_volume(body: dict[str, Any], change: VolumeChange) -> dict[str, Any]:
    """The item of a volume read, with the fields of the change set, locked when asked; its
    other people kept."""
    item = dict(body)
    item["Name"] = change.name
    item["IndexNumber"] = change.number
    item["Overview"] = change.summary
    others = [
        p for p in item.get("People") or [] if isinstance(p, dict) and p.get("Type") != "Author"
    ]
    item["People"] = [
        *({"Name": a, "Type": "Author", "Role": ""} for a in change.authors),
        *others,
    ]
    locked = set(item.get("LockedFields") or [])
    if change.lock:
        locked |= {"Name", "Overview", "Cast"}
    item["LockedFields"] = sorted(locked)
    return item


def jellyfin_down[**P, T](
    method: Callable[P, Coroutine[Any, Any, T]],
) -> Callable[P, Coroutine[Any, Any, T]]:
    """A method whose errors of Jellyfin raise LibraryUnavailableError."""

    @wraps(method)
    async def call(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await method(*args, **kwargs)
        except ServiceError as exc:
            raise LibraryUnavailableError(type(exc).__name__) from exc

    return call


class LibraryReader:
    """The series of the libraries of books of Jellyfin, read alone (a singleton)."""

    def __init__(self, jellyfin: JellyfinClient, settings: LibrarySettings) -> None:
        self.jellyfin = jellyfin
        self.settings = settings

    async def kinds(self) -> list[Shelf]:
        """The library of Jellyfin of each kind, and its folder; a kind without one is left."""
        url, key = await self.settings.jellyfin()
        libraries = await self.jellyfin.libraries(url, key)
        found: list[Shelf] = []
        for kind, root in (await self.settings.libraries()).items():
            try:
                library, location = library_of(root, libraries)
            except LookupError:
                continue
            if library.item_id is not None:
                found.append(
                    Shelf(kind=kind, item_id=library.item_id, library=library, location=location)
                )
        return found

    @jellyfin_down
    async def read(self) -> list[LibrarySeries]:
        """Every series of the libraries of each kind, by name."""
        url, key = await self.settings.jellyfin()
        series: list[LibrarySeries] = []
        for shelf in await self.kinds():
            items = await self.jellyfin.items(url, key, shelf.item_id, ITEM_TYPES)
            series += [s for s, _ in self.grouped(items, shelf.location, shelf.kind)]
        return sorted(series, key=lambda s: (s.name.casefold(), s.kind))

    def grouped(
        self, items: Sequence[JellyfinItem], location: str, kind: Kind
    ) -> list[tuple[LibrarySeries, list[JellyfinItem]]]:
        """The folders of the series of a library and the volumes under each."""
        folders = {i.path: i for i in items if i.type == "Folder"}
        volumes: dict[str, list[JellyfinItem]] = {}
        for item in items:
            if item.type not in VOLUME_TYPES:
                continue
            folder = series_folder(item.path, location, kind)
            if folder is not None and folder in folders:
                volumes.setdefault(folder, []).append(item)
        grouped: list[tuple[LibrarySeries, list[JellyfinItem]]] = []
        for path, books in volumes.items():
            owner = folders[path]
            books.sort(key=lambda b: (b.index_number is None, b.index_number or 0, b.name))
            authors = owner.authors or tuple(dict.fromkeys(a for b in books for a in b.authors))
            grouped.append(
                (
                    LibrarySeries(
                        id=owner.id,
                        kind=kind,
                        name=owner.name,
                        original_title=owner.original_title,
                        authors=authors,
                        year=owner.year,
                        genres=owner.genres,
                        summary=owner.overview,
                        has_image=owner.has_image,
                        volumes=len(books),
                        volumes_without_summary=sum(1 for b in books if not b.overview),
                        volumes_without_image=sum(1 for b in books if not b.has_image),
                        path=path,
                        image_tag=owner.image_tag,
                    ),
                    books,
                )
            )
        return grouped

    async def series(self, series_id: str) -> tuple[LibrarySeries, list[JellyfinItem]]:
        """A series and its volumes; raises SeriesNotFoundError."""
        url, key = await self.settings.jellyfin()
        for shelf in await self.kinds():
            items = await self.jellyfin.items(url, key, shelf.item_id, ITEM_TYPES)
            for found, books in self.grouped(items, shelf.location, shelf.kind):
                if found.id == series_id:
                    return found, books
        raise SeriesNotFoundError(series_id)

    async def volume(self, item_id: str) -> tuple[Shelf, JellyfinItem]:
        """A book or an audiobook of a library of books, and its library; raises
        VolumeNotFoundError (any other item of Jellyfin is never given)."""
        url, key = await self.settings.jellyfin()
        for shelf in await self.kinds():
            for item in await self.jellyfin.items(url, key, shelf.item_id, VOLUME_TYPES):
                if item.id == item_id and item.type in VOLUME_TYPES:
                    return shelf, item
        raise VolumeNotFoundError(item_id)

    async def refresh_changed(self, item_id: str) -> None:
        """The refresh of an item of Jellyfin after a change of shelfdrop, and of what it holds
        (F40): what depends on its fields follows them, nothing written is replaced. Jellyfin
        queues it; a failure is logged by its class and never fails the change."""
        try:
            url, key = await self.settings.jellyfin()
            await self.jellyfin.refresh(url, key, item_id, "changed")
        except ServiceError as exc:
            logger.warning(
                "Jellyfin refresh after a change failed", extra={"error": type(exc).__name__}
            )

    @jellyfin_down
    async def volumes_of(self, kind: Kind, name: str) -> set[int]:
        """The numbers of the volumes of the series `name` (by its folder, whatever its case) in
        the library of `kind`: their number in Jellyfin, else in their name."""
        url, key = await self.settings.jellyfin()
        for shelf in await self.kinds():
            if shelf.kind != kind:
                continue
            items = await self.jellyfin.items(url, key, shelf.item_id, ITEM_TYPES)
            for found, books in self.grouped(items, shelf.location, kind):
                if found.name.casefold() == name.casefold():
                    return {n for n in (number_of(b) for b in books) if n is not None}
        return set()


class LibraryService(LibraryReader):
    def __init__(
        self,
        jellyfin: JellyfinClient,
        settings: LibrarySettings,
        works: WorkFinder,
        images: ImageReader,
        placement: PlacementRepositoryFactory,
        clock: Clock,
    ) -> None:
        super().__init__(jellyfin, settings)
        self.works = works
        self.images = images
        self.placement = placement
        self.clock = clock

    @jellyfin_down
    async def proposals(self, series_id: str) -> SeriesProposals:
        """The images of its volumes, and the covers, the summaries and the names of its work:
        the one it was linked to, else the first the sources find under its name (none when no
        source answers)."""
        found, books = await self.series(series_id)
        return await self.proposals_of(found, books)

    async def proposals_of(
        self, found: LibrarySeries, books: Sequence[JellyfinItem]
    ) -> SeriesProposals:
        volumes = tuple(
            VolumeImage(item_id=b.id, label=volume_label(b, found.kind), image_tag=b.image_tag)
            for b in books
            if b.has_image
        )[:VOLUME_PROPOSALS]
        work, linked = await self.work_of(found)
        if work is None:
            return SeriesProposals(
                volumes=volumes, covers=(), summaries=(), work_id=None, linked=linked
            )
        return SeriesProposals(
            volumes=volumes,
            covers=tuple(SourceCover(source=s, url=u) for s, u in work.covers.items()),
            summaries=tuple(SourceSummary(source=s, text=t) for s, t in work.summaries.items()),
            work_id=work.id,
            work=work,
            linked=linked,
            names=work.names,
        )

    async def work_of(self, found: LibrarySeries) -> tuple[Work | None, bool]:
        """The work of a series and whether it was linked by hand: the work linked (read from
        the cache of the search, else searched again under its name: the work of the same
        id), else the first the sources find under the name of the series."""
        link = await self.on_shelf(lambda r: r.read_link(found.id))
        if link is not None:
            return await self.linked_work(link), True
        try:
            search = await self.works.search(found.name, found.kind)
        except (NoSourceAnsweredError, QueryTooShortError):
            return None, False
        return (search.works[0] if search.works else None), False

    async def linked_work(self, link: SeriesLink) -> Work | None:
        try:
            return await self.works.read_work(link.work_id)
        except WorkNotFoundError:
            pass
        try:
            search = await self.works.search(link.title, link.kind)
        except (NoSourceAnsweredError, QueryTooShortError):
            return None
        return next(
            (
                w
                for w in (*search.works, *search.other_forms)
                if w.id == link.work_id or link.work_id in w.keys
            ),
            None,
        )

    async def on_shelf[T](self, use: Callable[[PlacementRepository], T]) -> T:
        """`use` on a repository of its own, in the threadpool, committed."""

        def run() -> T:
            repository = self.placement()
            try:
                result = use(repository)
                repository.commit()
                return result
            finally:
                repository.close()

        return await anyio.to_thread.run_sync(run)

    @jellyfin_down
    async def link_work(self, series_id: str, work_id: str) -> SeriesProposals:
        """The series linked to the work `work_id` (found by a search in the last days), in
        the place of the one found under its name; the files placed of the series given to
        it. Raises SeriesNotFoundError, WorkNotFoundError."""
        found, books = await self.series(series_id)
        work = await self.works.read_work(work_id)
        roots = await self.settings.libraries()
        shelf = next((s for s in await self.kinds() if s.kind == found.kind), None)
        link = SeriesLink(
            series_id=found.id,
            kind=found.kind,
            work_id=work.id,
            title=work.shelf_name,
            updated_at=int(self.clock.now()),
        )

        def save(repository: PlacementRepository) -> None:
            repository.save_link(link)
            if shelf is not None:
                ids = [
                    f.id
                    for f in repository.read_files()
                    if f.kind == found.kind
                    and in_folder(f.path, roots[found.kind], shelf.location, found.path)
                ]
                repository.set_work(ids, work.id)

        await self.on_shelf(save)
        logger.info("Series linked to a work", extra={"kind": found.kind})
        return await self.proposals_of(found, books)

    @jellyfin_down
    async def unlink_work(self, series_id: str) -> SeriesProposals:
        """The link of the series undone: its work is again the first found under its name
        (its files placed keep their work). Raises SeriesNotFoundError."""
        found, books = await self.series(series_id)
        await self.on_shelf(lambda r: r.remove_link(found.id))
        return await self.proposals_of(found, books)

    @jellyfin_down
    async def adoption(self, series_id: str) -> SeriesAdoption:
        """The preview of the adoption of the volumes of a series: the number of each and the
        name it would take, and whether it is on the shelf already. Raises
        SeriesNotFoundError."""
        found, books = await self.series(series_id)
        work, _ = await self.work_of(found)
        url, key = await self.settings.jellyfin()
        locals_ = await self.local_paths(found, books)
        shelved = await self.on_shelf(lambda r: r.read_shelf_paths())
        sizes: dict[str, int | None] = {}
        limiter = anyio.CapacityLimiter(SIZE_READS)

        async def size(book: JellyfinItem) -> None:
            async with limiter:
                sizes[book.id] = await self.jellyfin.file_size(url, key, book.id)

        async with anyio.create_task_group() as group:
            for book in books:
                group.start_soon(size, book)
        return SeriesAdoption(
            series_id=found.id,
            work_id=None if work is None else work.id,
            files=tuple(
                adoption_file(b, found.name, sizes.get(b.id), locals_.get(b.id) in shelved)
                for b in books
            ),
        )

    async def local_paths(
        self, found: LibrarySeries, books: Sequence[JellyfinItem]
    ) -> dict[str, str]:
        """The file of each volume, as the placement worker sees it (by item id); a volume out
        of the folder of its kind is left."""
        roots = await self.settings.libraries()
        libraries = [s.library for s in await self.kinds() if s.kind == found.kind]
        paths: dict[str, str] = {}
        for book in books:
            try:
                paths[book.id] = to_local(book.path, {found.kind: roots[found.kind]}, libraries)
            except LookupError:
                continue
        return paths

    @jellyfin_down
    async def adopt(
        self, series_id: str, choices: Sequence[AdoptionChoice], *, place: bool
    ) -> AdoptionResult:
        """The volumes of a series chosen recorded on the shelf as files of its work, under
        the numbers confirmed; with `place`, renamed first by the placement worker to the
        names of the shelf, in their folder, never over a file (a name taken by another file
        of the folder is reported, the file adopted under its name). Nothing is done when a
        file is refused. Raises SeriesNotFoundError, AdoptionRefusedError."""
        found, books = await self.series(series_id)
        work, _ = await self.work_of(found)
        if work is None:
            raise AdoptionRefusedError("no_work")
        by_id = {b.id: b for b in books}
        chosen = [c for c in choices if c.include]
        unknown = tuple(c.item_id for c in chosen if c.item_id not in by_id)
        if unknown:
            raise AdoptionRefusedError("unknown", unknown)
        unnumbered = tuple(c.item_id for c in chosen if c.volume is None and c.chapter is None)
        if unnumbered:
            raise AdoptionRefusedError("unnumbered", unnumbered)
        locals_ = await self.local_paths(found, books)
        missing = tuple(c.item_id for c in chosen if c.item_id not in locals_)
        if missing:
            raise AdoptionRefusedError("unknown", missing)
        files = await self.on_shelf(lambda r: r.read_files())
        shelved = {f.path for f in files}
        adopted = tuple(c.item_id for c in chosen if locals_[c.item_id] in shelved)
        if adopted:
            raise AdoptionRefusedError("adopted", adopted)
        roots = await self.settings.libraries()
        shelf = next((s for s in await self.kinds() if s.kind == found.kind), None)
        on_shelf = {
            (f.volume, f.chapter)
            for f in files
            if f.kind == found.kind
            and (
                f.work_id == work.id
                or (
                    shelf is not None
                    and in_folder(f.path, roots[found.kind], shelf.location, found.path)
                )
            )
        }
        duplicate = duplicates(chosen, on_shelf)
        if duplicate:
            raise AdoptionRefusedError("duplicate", duplicate)
        author = found.authors[0] if found.authors else ""
        placed: list[PlacedFile] = []
        targets: list[str] = []
        conflicts: list[str] = []
        taken = {b.path for b in books}
        for choice in chosen:
            book = by_id[choice.item_id]
            local = PurePosixPath(locals_[choice.item_id])
            name = adopted_name(found.name, choice.volume, choice.chapter, local.suffix)
            target = str(local.parent / name)
            seen = str(PurePosixPath(book.path).parent / name)
            if place and seen != book.path and seen in taken:
                conflicts.append(choice.item_id)
                target = str(local)
            taken.add(seen)
            placed.append(
                PlacedFile(
                    download_id=None,
                    kind=found.kind,
                    work_id=work.id,
                    series=found.name,
                    author=author,
                    volume=choice.volume,
                    chapter=choice.chapter,
                    path=str(local),
                )
            )
            targets.append(target)
        now = int(self.clock.now())
        if place:
            order = AdoptOrder(series_id=found.id, files=tuple(placed), targets=tuple(targets))
            await self.on_shelf(lambda r: r.add_adoption(order, now))
        else:
            await self.on_shelf(lambda r: r.add_files(placed, now))
        logger.info("Files adopted", extra={"files": len(placed), "renamed": place})
        return AdoptionResult(adopted=len(placed), renamed=place, conflicts=tuple(conflicts))

    @jellyfin_down
    async def volumes(self, series_id: str) -> SeriesVolumes:
        """A series, its volumes with the size of their file, and the numbers missing."""
        found, books = await self.series(series_id)
        url, key = await self.settings.jellyfin()
        sizes: dict[str, int | None] = {}
        limiter = anyio.CapacityLimiter(SIZE_READS)

        async def size(book: JellyfinItem) -> None:
            async with limiter:
                sizes[book.id] = await self.jellyfin.file_size(url, key, book.id)

        async with anyio.create_task_group() as group:
            for book in books:
                group.start_soon(size, book)
        return SeriesVolumes(
            series=found,
            volumes=tuple(volume_of(b, sizes.get(b.id)) for b in books),
            missing=missing_numbers([number_of(b) for b in books]),
        )

    @jellyfin_down
    async def download(self, item_id: str) -> VolumeFile:
        """The file of a volume, as Jellyfin sends it; raises VolumeNotFoundError."""
        _, found = await self.volume(item_id)
        url, key = await self.settings.jellyfin()
        try:
            read = await self.jellyfin.download(url, key, item_id)
        except ServiceError as exc:
            if exc.status == 404:
                raise VolumeNotFoundError(item_id) from exc
            raise
        return VolumeFile(name=PurePosixPath(found.path).name, file=read)

    @jellyfin_down
    async def change_volume(self, item_id: str, change: VolumeChange) -> LibraryVolume:
        """The change of a volume, then the volume read again (its new image tag with it), then
        its refresh in Jellyfin."""
        await self.volume(item_id)
        picture = await self.picture(change.image) if change.image is not None else None
        url, key = await self.settings.jellyfin()
        body = await self.jellyfin.item(url, key, item_id)
        await self.jellyfin.update_item(url, key, item_id, changed_volume(body, change))
        if picture is not None:
            await self.jellyfin.set_image(url, key, item_id, *picture)
        _, changed = await self.volume(item_id)
        read = volume_of(changed, await self.jellyfin.file_size(url, key, item_id))
        await self.refresh_changed(item_id)
        return read

    @jellyfin_down
    async def image(self, item_id: str, width: int) -> tuple[bytes, str]:
        """The image of an item of Jellyfin, for the page."""
        url, key = await self.settings.jellyfin()
        return await self.jellyfin.image(url, key, item_id, width)

    async def picture(self, choice: ImageChoice) -> tuple[bytes, str]:
        """The bytes and the type of the image chosen; raises ImageRefusedError."""
        match choice:
            case ItemImage(item_id=item_id):
                try:
                    data, _ = await self.image(item_id, IMAGE_WIDTH)
                except LibraryUnavailableError as exc:
                    raise ImageRefusedError(item_id) from exc
            case LinkImage(url=link):
                read = await self.images.image(link)
                if read is None:
                    raise ImageRefusedError(link)
                data = read
            case SentImage(data=sent):
                data = sent
        kind = picture_of(data)
        if kind is None or len(data) > IMAGE_MAX_BYTES:
            raise ImageRefusedError("not a picture")
        return data, kind[1]

    @jellyfin_down
    async def change(self, series_id: str, change: SeriesChange) -> LibrarySeries:
        """The change of a series, then the series read again (its new image tag with it), then
        the refresh of its folder in Jellyfin."""
        found, books = await self.series(series_id)
        picture = await self.picture(change.image) if change.image is not None else None
        url, key = await self.settings.jellyfin()
        body = await self.jellyfin.item(url, key, series_id)
        await self.jellyfin.update_item(
            url, key, series_id, changed_item(body, change, fields=True, summary=True)
        )
        if change.summary_to_volumes and change.summary:
            for book in books:
                if not book.overview:
                    read = await self.jellyfin.item(url, key, book.id)
                    await self.jellyfin.update_item(
                        url, key, book.id, changed_item(read, change, fields=False, summary=True)
                    )
        if picture is not None:
            data, content_type = picture
            if change.image_to_series:
                await self.jellyfin.set_image(url, key, series_id, data, content_type)
            if change.image_to_volumes:
                for book in books:
                    if not book.has_image:
                        await self.jellyfin.set_image(url, key, book.id, data, content_type)
            if change.save_cover:
                await self.ask_cover(found.path, data)
        changed, _ = await self.series(series_id)
        await self.refresh_changed(series_id)
        return changed

    async def ask_cover(self, path: str, data: bytes) -> None:
        """The `cover.jpg` of the folder `path` (as Jellyfin sees it), written by the worker."""

        def add() -> None:
            repository = self.placement()
            try:
                repository.add_task("cover", path, data, int(self.clock.now()))
                repository.commit()
            finally:
                repository.close()

        await anyio.to_thread.run_sync(add)

    @jellyfin_down
    async def fill(self, summaries: Mapping[str, str]) -> int:
        """The summaries given, set on their series without one and on their volumes without
        one, locked; the number of series changed."""
        url, key = await self.settings.jellyfin()
        changed = 0
        for shelf in await self.kinds():
            items = await self.jellyfin.items(url, key, shelf.item_id, ITEM_TYPES)
            for found, books in self.grouped(items, shelf.location, shelf.kind):
                text = summaries.get(found.id, "").strip()
                if not text:
                    continue
                change = summary_change(text)
                targets = [found.id] if not found.summary else []
                targets += [b.id for b in books if not b.overview]
                for item_id in targets:
                    body = await self.jellyfin.item(url, key, item_id)
                    await self.jellyfin.update_item(
                        url, key, item_id, changed_item(body, change, fields=False, summary=True)
                    )
                changed += 1
        return changed

    @jellyfin_down
    async def scan(self, order: ScanOrder) -> None:
        """A series, a library, or every library scanned in the mode of the order."""
        url, key = await self.settings.jellyfin()
        if order.series_id is not None:
            await self.series(order.series_id)
            await self.jellyfin.refresh(url, key, order.series_id, order.mode)
            return
        kinds = await self.kinds()
        if order.kind is None and order.mode == "new":
            await self.jellyfin.refresh_libraries(url, key)
            return
        for shelf in kinds:
            if order.kind in (None, shelf.kind):
                await self.jellyfin.refresh(url, key, shelf.item_id, order.mode)

    @jellyfin_down
    async def scanning(self) -> dict[Kind, float | None]:
        """The progress of the scan of the library of each kind (0 to 100), None when idle."""
        return {shelf.kind: shelf.library.refresh_progress for shelf in await self.kinds()}


def in_folder(path: str, root: str, location: str, folder: str) -> bool:
    """Whether a file placed (`path`, as the worker sees it, under `root`) is in the folder of
    a series (`folder`, as Jellyfin sees it, under `location`)."""
    try:
        return to_jellyfin(path, root, location).startswith(f"{folder}/")
    except ValueError:
        return False


def adoption_file(book: JellyfinItem, series: str, size: int | None, adopted: bool) -> AdoptionFile:
    """A volume as an adoption would take it: its `IndexNumber`, else a chapter, else a volume
    its file name gives (the parsers of the placement), else no number."""
    path = PurePosixPath(book.path)
    volume: int | None = None
    chapter: float | None = None
    origin: NumberOrigin | None = None
    if book.index_number is not None:
        volume, origin = book.index_number, "jellyfin"
    else:
        chapter = file_chapter(path.stem)
        volume = None if chapter is not None else file_volume(path.stem)
        origin = None if chapter is None and volume is None else "name"
    target = (
        None
        if volume is None and chapter is None
        else adopted_name(series, volume, chapter, path.suffix)
    )
    return AdoptionFile(
        item_id=book.id,
        path=book.path,
        size=size,
        volume=volume,
        chapter=chapter,
        origin=origin,
        target=target,
        adopted=adopted,
    )


def duplicates(
    chosen: Sequence[AdoptionChoice], on_shelf: set[tuple[int | None, float | None]]
) -> tuple[str, ...]:
    """The files chosen whose number another file chosen, or a file of the shelf, holds."""
    counts: dict[tuple[int | None, float | None], int] = {}
    for choice in chosen:
        key = (None if choice.chapter is not None else choice.volume, choice.chapter)
        counts[key] = counts.get(key, 0) + 1
    shelf = {(None if c is not None else v, c) for v, c in on_shelf}
    return tuple(
        c.item_id
        for c in chosen
        if (key := (None if c.chapter is not None else c.volume, c.chapter)) in shelf
        or counts[key] > 1
    )


def volume_of(item: JellyfinItem, size: int | None) -> LibraryVolume:
    return LibraryVolume(
        id=item.id,
        type=item.type,
        name=item.name,
        number=item.index_number,
        summary=item.overview,
        authors=item.authors,
        has_image=item.has_image,
        file_name=PurePosixPath(item.path).name,
        size=size,
        image_tag=item.image_tag,
    )


def summary_change(text: str) -> SeriesChange:
    """A change of the summary alone, locked."""
    return SeriesChange(
        name="",
        original_title="",
        authors=(),
        year=None,
        genres=(),
        summary=text,
        lock=True,
        summary_to_volumes=True,
        image=None,
        image_to_series=False,
        image_to_volumes=False,
        save_cover=False,
    )
