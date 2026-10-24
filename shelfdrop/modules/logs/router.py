"""The route of the logs (the page Paramètres, Journaux): the records of the API and of the
placement worker, read from their files (ADR 0023). Kept for the session of an administrator: a
record may name a work, an account, a file."""

from typing import Annotated, Final, Literal

from fastapi import APIRouter, Query
from wireup import Injected
from wireup.integration.fastapi import WireupRoute

from shelfdrop.logs.service import LogReader
from shelfdrop.logs.types import LogCursor, LogEntry, LogProcess, LogQuery
from shelfdrop.modules.logs.schemas import LogEntryRead, LogsRead

router = APIRouter(prefix="/v1/logs", tags=["logs"], route_class=WireupRoute)

# A cursor of the page: the timestamp of its last entry, then its place among those of that time.
CURSOR_PATTERN: Final = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00~[1-9]\d{0,6}$"

Level = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def cursor_of(before: str | None) -> LogCursor | None:
    if before is None:
        return None
    timestamp, seen = before.rsplit("~", 1)
    return LogCursor(timestamp, int(seen))


def entry_read(entry: LogEntry) -> LogEntryRead:
    return LogEntryRead(
        timestamp=entry.timestamp,
        level=entry.level,
        logger=entry.logger,
        message=entry.message,
        request_id=entry.request_id,
        fields=dict(entry.fields),
    )


@router.get("")
def read_logs(
    reader: Injected[LogReader],
    service: Annotated[
        LogProcess, Query(description="The service of Compose whose records are read.")
    ] = LogProcess.API,
    level: Annotated[Level, Query(description="The lowest level shown.")] = "DEBUG",
    text: Annotated[
        str | None,
        Query(
            max_length=200,
            description="Searched, without case, in the message, the logger, the request id "
            "and the other fields.",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    before: Annotated[
        str | None,
        Query(pattern=CURSOR_PATTERN, description="The `next` of the previous page."),
    ] = None,
) -> LogsRead:
    """The records of a process, the newest first: those of its file and of its two rotated
    copies (15 MiB at most)."""
    page = reader.read(LogQuery(service, level, text or None, limit, cursor_of(before)))
    return LogsRead(
        entries=[entry_read(entry) for entry in page.entries],
        next=None if page.next is None else f"{page.next.timestamp}~{page.next.seen}",
    )
