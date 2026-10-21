"""WorkCovers: the cover of a work the search found, at its sources (its `cover_url`), for the
placement of an audiobook without a picture and for the proposals of the page Métadonnées."""

import logging
from typing import Final

import anyio
import anyio.to_thread
import httpx

from shelfdrop.utils.pictures import picture_of
from shelfdrop.works.repository import WorkRepositoryFactory
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)

# A cover larger than this is not taken.
COVER_MAX_BYTES: Final = 5 * 1024 * 1024


class WorkCovers:
    def __init__(
        self, repositories: WorkRepositoryFactory, http: httpx.AsyncClient, clock: Clock
    ) -> None:
        self.repositories = repositories
        self.http = http
        self.clock = clock

    async def cover(self, work_id: str) -> bytes | None:
        """The cover of a work kept from a search (7 days), None without one."""

        def read() -> str | None:
            repository = self.repositories()
            try:
                work = repository.read_work(work_id, int(self.clock.now()))
            finally:
                repository.close()
            return None if work is None else work.cover_url

        url = await anyio.to_thread.run_sync(read)
        return None if url is None else await self.image(url)

    async def image(self, url: str) -> bytes | None:
        """The picture at `url` (a JPEG, a PNG or a WebP, 5 MB at most), None otherwise."""
        try:
            response = await self.http.get(url)
        except httpx.HTTPError as exc:
            logger.info("Cover not read", extra={"error": type(exc).__name__})
            return None
        if response.status_code != 200 or len(response.content) > COVER_MAX_BYTES:
            return None
        # The picture by its first bytes, whatever its type says.
        return response.content if picture_of(response.content) is not None else None
