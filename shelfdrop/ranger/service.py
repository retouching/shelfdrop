"""RangerService: the page Ranger: the files to place by hand, the
files of the shelf to correct, and what the page asks the placement worker to do with them. The
API never writes in the libraries: the worker does (`shelfdrop.placement.byhand`)."""

from collections.abc import Callable
from dataclasses import dataclass

import anyio.to_thread

from shelfdrop.placement.repository import PlacementRepository, PlacementRepositoryFactory
from shelfdrop.placement.types import (
    ChaptersRequest,
    ItemState,
    NewItem,
    PlaceItem,
    PlaceRequest,
    ShelfFile,
    VolumeRequest,
)
from shelfdrop.ranger.exceptions import (
    ItemBusyError,
    ItemNotFoundError,
    ItemNotIgnoredError,
    RequestRefusedError,
)
from shelfdrop.works.types import Clock

# The files of the shelf a search of the page lists at most.
SHELF_LIMIT = 50


@dataclass(frozen=True, kw_only=True)
class Listing:
    """The files of Ranger, and the files of the shelf whose path holds the text searched."""

    items: list[PlaceItem]
    shelved: list[ShelfFile]


def check(item: PlaceItem, request: PlaceRequest) -> None:
    """Raises RequestRefusedError when `request` does not fit `item`."""
    if isinstance(request, ChaptersRequest):
        if item.state != "chapters":
            raise RequestRefusedError("not a release in chapters")
        ranges = sorted((v.first, v.last) for v in request.volumes)
        numbers = [v.volume for v in request.volumes]
        if len(set(numbers)) != len(numbers) or any(first > last for first, last in ranges):
            raise RequestRefusedError("volumes repeated, or a range upside down")
        if any(ranges[n][0] <= ranges[n - 1][1] for n in range(1, len(ranges))):
            raise RequestRefusedError("ranges overlap")
        if not request.volumes and request.rest == "keep":
            raise RequestRefusedError("nothing to place")
    elif item.state == "chapters" and isinstance(request, VolumeRequest):
        raise RequestRefusedError("a release in chapters goes to its volumes")


def open_state(item: PlaceItem) -> ItemState:
    """The state an ignored file takes back: a release in chapters keeps its chapters, a file of
    the libraries is misplaced, any other is to link."""
    if item.chapters:
        return "chapters"
    return "misplaced" if item.origin == "library" else "unlinked"


class RangerService:
    def __init__(self, repositories: PlacementRepositoryFactory, clock: Clock) -> None:
        self.repositories = repositories
        self.clock = clock

    async def read(self, text: str) -> Listing:
        """The files to place and those placed; with `text`, the files of the shelf whose path
        holds it too."""
        needle = text.strip()

        def run(repository: PlacementRepository) -> Listing:
            items = repository.read_items(placed=True)
            shelved = repository.find_shelved(needle, SHELF_LIMIT) if needle else []
            return Listing(items=items, shelved=shelved)

        return await self.on_shelf(run, commit=False)

    async def count(self) -> int:
        return await self.on_shelf(lambda r: r.count_open(), commit=False)

    async def link(self, item_id: int, request: PlaceRequest) -> PlaceItem:
        """`request` given to the worker for the file `item_id`. Raises ItemNotFoundError,
        ItemBusyError, RequestRefusedError."""
        now = int(self.clock.now())

        def run(repository: PlacementRepository) -> PlaceItem:
            item = repository.read_item(item_id)
            if item is None:
                raise ItemNotFoundError(item_id)
            check(item, request)
            if not repository.ask(item_id, request, now):
                raise ItemBusyError(item_id)
            asked = repository.read_item(item_id)
            if asked is None:
                raise ItemNotFoundError(item_id)
            return asked

        return await self.on_shelf(run)

    async def resume(self, item_id: int) -> PlaceItem:
        """An ignored file back among the files to place; its download, placed meanwhile,
        stays placed. Raises ItemNotFoundError, ItemNotIgnoredError."""
        now = int(self.clock.now())

        def run(repository: PlacementRepository) -> PlaceItem:
            item = repository.read_item(item_id)
            if item is None:
                raise ItemNotFoundError(item_id)
            if item.state != "ignored" or not repository.resume(item_id, open_state(item), now):
                raise ItemNotIgnoredError(item_id)
            resumed = repository.read_item(item_id)
            if resumed is None:
                raise ItemNotFoundError(item_id)
            return resumed

        return await self.on_shelf(run)

    async def relink(self, file_id: int, request: VolumeRequest) -> PlaceItem:
        """A file of the shelf placed again under another work or volume: a file of Ranger
        from the libraries, moved by the worker. Raises ItemNotFoundError."""
        now = int(self.clock.now())

        def run(repository: PlacementRepository) -> PlaceItem:
            shelved = repository.read_shelf_file(file_id)
            if shelved is None:
                raise ItemNotFoundError(file_id)
            name = shelved.path.rsplit("/", 1)[-1]
            item_id = repository.add_item(
                NewItem(
                    origin="library",
                    download_id=None,
                    kind=shelved.kind,
                    name=name,
                    path=shelved.path,
                    files=(shelved.path,),
                    size=0,
                    state="misplaced",
                    reason="relink",
                    series=shelved.series,
                    work_id=shelved.work_id,
                    author=shelved.author,
                ),
                now,
            )
            repository.ask(item_id, request, now)
            item = repository.read_item(item_id)
            if item is None:
                raise ItemNotFoundError(item_id)
            return item

        return await self.on_shelf(run)

    async def scan(self) -> None:
        """A scan of the libraries asked to the worker, unless one waits already."""
        now = int(self.clock.now())

        def run(repository: PlacementRepository) -> None:
            if not repository.has_pending_scan():
                repository.add_task("scan", "", b"", now)

        await self.on_shelf(run)

    async def on_shelf[T](
        self, use: Callable[[PlacementRepository], T], *, commit: bool = True
    ) -> T:
        def run() -> T:
            repository = self.repositories()
            try:
                result = use(repository)
                if commit:
                    repository.commit()
                return result
            finally:
                repository.close()

        return await anyio.to_thread.run_sync(run)
