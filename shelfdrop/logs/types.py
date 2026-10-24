"""Types of the logs read by the page: a process, a query, an entry, a page of entries."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class LogProcess(StrEnum):
    """The processes that write a file of logs (`shelfdrop.logging.setup.log_file`)."""

    API = "api"
    PLACEMENT = "placement"


@dataclass(frozen=True, slots=True)
class LogCursor:
    """Where a page ends: the entries older than `timestamp`, and those of `timestamp` after the
    first `seen` of the file, are the next ones."""

    timestamp: str
    seen: int


@dataclass(frozen=True, slots=True)
class LogQuery:
    process: LogProcess
    # A stdlib level name: the entries of this level and above.
    level: str
    # Searched in the message, the logger, the request id and the other fields, without case.
    text: str | None
    limit: int
    before: LogCursor | None


@dataclass(frozen=True, slots=True)
class LogEntry:
    timestamp: str
    level: str
    logger: str
    message: str
    request_id: str | None
    # The other fields of the record (`extra`, `exception`, `stack`), as JSON values.
    fields: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class LogPage:
    """The entries, the newest first, and the cursor of the older ones (None: no more)."""

    entries: list[LogEntry]
    next: LogCursor | None
