"""DownloadCovers: the cover of the work of an automatic download, for the journal (the events
`sent` and `downloaded`) and for the page (a container singleton).

A cover is read once for its work, then kept a while in memory (`KEPT_SECONDS`, `KEPT_BYTES` at
most), so that the downloads of one request do not each fetch it again. An event takes it only
when its group had none for half the batch window of the journal: every message of a group
shows it, but the same picture is not kept with each of its 22 events. A cover that fails is
none: it never holds up a send nor a completion.
"""

import dataclasses
import logging
from collections import OrderedDict
from typing import Final, Protocol

from shelfdrop.downloads.types import Download
from shelfdrop.journal.types import NewEvent
from shelfdrop.works.types import Clock

logger = logging.getLogger(__name__)

# How long a cover read stays in memory, and how many bytes of covers at most.
KEPT_SECONDS: Final = 3600.0
KEPT_BYTES: Final = 16 * 1024 * 1024
# The groups remembered at most (the last ones a cover went to).
KEPT_GROUPS: Final = 256
# The events of the journal that carry the cover of the work.
WITH_COVER: Final = frozenset({"sent", "downloaded"})


class WorkCoverSource(Protocol):
    """The cover of a work at its sources (the work search), None without one."""

    async def cover(self, work_id: str) -> bytes | None: ...


class DownloadCovers:
    def __init__(self, source: WorkCoverSource, clock: Clock, batch_seconds: int) -> None:
        self.source = source
        self.clock = clock
        # A group takes the cover again after this long: a message of the journal gathers the
        # events of `batch_seconds`, so each message of the group finds one.
        self.repeat_seconds = batch_seconds / 2
        self.covers: OrderedDict[str, tuple[float, bytes | None]] = OrderedDict()
        self.groups: OrderedDict[str, float] = OrderedDict()

    async def cover(self, download: Download) -> bytes | None:
        """The cover of the work of `download`, None for a manual one, one without a work, or
        a cover the sources do not give."""
        if download.mode != "auto" or not download.work_id:
            return None
        work_id = download.work_id
        now = self.clock.now()
        kept = self.covers.get(work_id)
        if kept is not None and now - kept[0] < KEPT_SECONDS:
            return kept[1]
        try:
            data = await self.source.cover(work_id)
        except Exception as exc:
            logger.info("Cover of a download not read", extra={"error": type(exc).__name__})
            data = None
        self.keep(work_id, now, data)
        return data

    def keep(self, work_id: str, now: float, data: bytes | None) -> None:
        self.covers.pop(work_id, None)
        self.covers[work_id] = (now, data)
        while len(self.covers) > 1 and (
            sum(len(d or b"") for _, d in self.covers.values()) > KEPT_BYTES
        ):
            self.covers.popitem(last=False)

    async def dress(self, download: Download, event: NewEvent) -> NewEvent:
        """`event` with the cover of the work of `download`, when it is a `sent` or a
        `downloaded` of an automatic download and its group had none for a while."""
        if event.type not in WITH_COVER or download.mode != "auto" or not download.work_id:
            return event
        now = self.clock.now()
        last = self.groups.get(event.group)
        if last is not None and now - last < self.repeat_seconds:
            return event
        # Taken before the read: the sends of one request running at once ask it once.
        self.groups.pop(event.group, None)
        self.groups[event.group] = now
        while len(self.groups) > KEPT_GROUPS:
            self.groups.popitem(last=False)
        data = await self.cover(download)
        if data is None:
            self.groups.pop(event.group, None)
            return event
        return dataclasses.replace(event, cover=data)
