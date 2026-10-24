"""LibrarySync: the metadata of the files placed by shelfdrop sent again to Jellyfin, for a
series or for every library, asked from the page Jellyfin (ADR 0016). Through the API of
Jellyfin alone: the API never touches the files. A singleton: the sync runs in the background,
one at a time, and its state stays in memory."""

import asyncio
import contextlib
import logging
from collections.abc import Sequence

import anyio.to_thread

from shelfdrop.clients.exceptions import ServiceError
from shelfdrop.library.exceptions import LibraryUnavailableError
from shelfdrop.library.service import (
    ITEM_TYPES,
    VOLUME_TYPES,
    LibraryReader,
    PlacementRepositoryFactory,
    series_folder,
)
from shelfdrop.library.types import LibrarySeries, SyncStage, SyncState
from shelfdrop.placement.metadata import locked_item
from shelfdrop.placement.paths import to_jellyfin
from shelfdrop.placement.types import ShelfFile
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)


def volumes_of(placed: ShelfFile, files: Sequence[ShelfFile]) -> list[int]:
    """The volumes on the shelf of the work of a file (by its id, or by its series without
    one), as `PlacementRepository.read_shelved` finds them."""
    return sorted(
        {
            f.volume
            for f in files
            if f.kind == placed.kind
            and (
                f.work_id == placed.work_id
                if placed.work_id is not None
                else f.series == placed.series
            )
            and f.volume is not None
            and f.chapter is None
        }
    )


class LibrarySync:
    def __init__(
        self,
        reader: LibraryReader,
        placement: PlacementRepositoryFactory,
        clock: Clock,
    ) -> None:
        self.reader = reader
        self.placement = placement
        self.clock = clock
        self.current = SyncState(stage="idle")
        self.task: asyncio.Task[None] | None = None

    def state(self) -> SyncState:
        return self.current

    async def start(self, series_id: str | None) -> SyncState:
        """The sync of a series (raises SeriesNotFoundError, LibraryUnavailableError) or of
        every library, started in the background; while one runs, nothing more is started and
        its state is given."""
        if self.current.stage == "running":
            return self.current
        series: LibrarySeries | None = None
        if series_id is not None:
            try:
                series, _ = await self.reader.series(series_id)
            except ServiceError as exc:
                raise LibraryUnavailableError(type(exc).__name__) from exc
        self.current = SyncState(
            stage="running", series_id=series_id, started_at=int(self.clock.now())
        )
        self.task = asyncio.get_running_loop().create_task(self.run(series))
        return self.current

    async def close(self) -> None:
        """Stop the sync running (at the stop of the API)."""
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

    async def run(self, series: LibrarySeries | None) -> None:
        try:
            await self.sync(series)
        except Exception as exc:
            # A sync that fails ends, logged by its class: it is never left running.
            logger.warning("Library sync failed", extra={"error": type(exc).__name__})
            self.current = self.ended("failed")
        else:
            logger.info(
                "Library sync done",
                extra={"changed": self.current.changed, "not_found": self.current.not_found},
            )
            self.current = self.ended("done")

    def ended(self, stage: SyncStage) -> SyncState:
        return SyncState(
            stage=stage,
            series_id=self.current.series_id,
            changed=self.current.changed,
            unchanged=self.current.unchanged,
            not_found=self.current.not_found,
            started_at=self.current.started_at,
            ended_at=int(self.clock.now()),
        )

    def counted(self, *, changed: int = 0, unchanged: int = 0, not_found: int = 0) -> None:
        state = self.current
        self.current = SyncState(
            stage=state.stage,
            series_id=state.series_id,
            changed=state.changed + changed,
            unchanged=state.unchanged + unchanged,
            not_found=state.not_found + not_found,
            started_at=state.started_at,
        )

    async def sync(self, series: LibrarySeries | None) -> None:
        """Each file placed of the series (or of every library) that Jellyfin lists by its
        path: its name, series, number, sort and authors set as the placement sets them, the
        authors of shelfdrop over those of Jellyfin, `Name` and `Cast` locked, its image left;
        whatever the setting `placement.lock_jellyfin` says (the sync is asked). Then the
        folder of each series whose items changed refreshed in Jellyfin, once (F40)."""
        jellyfin = self.reader.jellyfin
        url, key = await self.reader.settings.jellyfin()
        roots = await self.reader.settings.libraries()
        files = await anyio.to_thread.run_sync(self.read_files)
        administrator: str | None = None
        synced: list[int] = []
        # The folders of the series whose items changed, in their order.
        touched: dict[str, None] = {}
        for shelf in await self.reader.kinds():
            if series is not None and shelf.kind != series.kind:
                continue
            placed = [f for f in files if f.kind == shelf.kind]
            if not placed:
                continue
            items = await jellyfin.items(url, key, shelf.item_id, ITEM_TYPES)
            by_path = {item.path: item for item in items if item.type in VOLUME_TYPES}
            folders = {item.path: item.id for item in items if item.type == "Folder"}
            for entry in placed:
                try:
                    path = to_jellyfin(entry.path, roots[shelf.kind], shelf.location)
                except ValueError:
                    # Out of the folder of its kind (the folder moved): not in Jellyfin.
                    path = ""
                if series is not None and not path.startswith(f"{series.path}/"):
                    continue
                item = by_path.get(path)
                if item is None:
                    self.counted(not_found=1)
                    continue
                if administrator is None:
                    administrator = await jellyfin.administrator(url, key)
                body = await jellyfin.item(url, key, item.id, administrator)
                wanted = locked_item(body, entry, volumes_of(entry, files), forced=True)
                if wanted == body:
                    self.counted(unchanged=1)
                else:
                    await jellyfin.update_item(url, key, item.id, wanted)
                    self.counted(changed=1)
                    folder = series_folder(item.path, shelf.location, shelf.kind)
                    if folder is not None and folder in folders:
                        touched[folders[folder]] = None
                synced.append(entry.id)
        if synced:
            await anyio.to_thread.run_sync(self.mark_locked, synced)
        for folder_id in touched:
            await self.reader.refresh_changed(folder_id)

    def read_files(self) -> list[ShelfFile]:
        repository = self.placement()
        try:
            return repository.read_files()
        finally:
            repository.close()

    def mark_locked(self, file_ids: list[int]) -> None:
        repository = self.placement()
        try:
            repository.mark_locked(file_ids)
            repository.commit()
        finally:
            repository.close()
