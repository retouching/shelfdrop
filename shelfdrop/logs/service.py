"""LogReader: the files of logs of the API and of the placement worker, read from their end
(ADR 0023). A file and its rotated copies (`api.jsonl`, `api.jsonl.1`, `api.jsonl.2`) are read
the newest first, block by block, and a file older than the page asked is opened but not read."""

import contextlib
import json
import logging
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import BinaryIO, Final

from shelfdrop.logs.types import LogCursor, LogEntry, LogPage, LogProcess, LogQuery

# The bytes read at once from the end of a file.
BLOCK_BYTES: Final = 64 * 1024
# The fields of a record that have their own place in an entry.
OWN_FIELDS: Final = frozenset({"timestamp", "level", "logger", "message", "request_id"})
LEVELS: Final = logging.getLevelNamesMapping()


def lines_backwards(file: BinaryIO) -> Iterator[bytes]:
    """The lines of a file, the last first, read block by block from its end."""
    file.seek(0, os.SEEK_END)
    end = file.tell()
    rest = b""
    while end > 0:
        start = max(0, end - BLOCK_BYTES)
        file.seek(start)
        lines = (file.read(end - start) + rest).split(b"\n")
        end = start
        rest = lines[0]
        for line in reversed(lines[1:]):
            if line:
                yield line
    if rest:
        yield rest


def first_timestamp(file: BinaryIO) -> str | None:
    """The time of the first record of a file; None when it has none readable."""
    file.seek(0)
    entry = entry_of(file.readline())
    return None if entry is None else entry.timestamp


def entry_of(line: bytes) -> LogEntry | None:
    """The entry of a line of JsonFormatter; None for anything else (a line cut while written)."""
    try:
        record = json.loads(line)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    timestamp, level, logger, message = (
        record.get(key) for key in ("timestamp", "level", "logger", "message")
    )
    request_id = record.get("request_id")
    if not (
        isinstance(timestamp, str)
        and isinstance(level, str)
        and isinstance(logger, str)
        and isinstance(message, str)
        and (request_id is None or isinstance(request_id, str))
    ):
        return None
    fields = {key: value for key, value in record.items() if key not in OWN_FIELDS}
    return LogEntry(timestamp, level, logger, message, request_id, fields)


def matches(entry: LogEntry, query: LogQuery) -> bool:
    if LEVELS.get(entry.level, 0) < LEVELS[query.level]:
        return False
    if not query.text:
        return True
    needle = query.text.casefold()
    haystack = (
        entry.message,
        entry.logger,
        entry.request_id or "",
        json.dumps(entry.fields, ensure_ascii=False, default=str),
    )
    return any(needle in part.casefold() for part in haystack)


class LogReader:
    def __init__(self, files: Mapping[LogProcess, Path]) -> None:
        self.files = files

    def read(self, query: LogQuery) -> LogPage:
        """The entries of a process that match, the newest first; a process that never wrote
        has none."""
        entries: list[LogEntry] = []
        # The place of each entry kept among those of its timestamp, for the cursor.
        places: list[int] = []
        previous: str | None = None
        seen = 0
        before = query.before
        for entry in self.entries(self.files[query.process], before):
            seen = seen + 1 if entry.timestamp == previous else 1
            previous = entry.timestamp
            if before is not None and (
                entry.timestamp > before.timestamp
                or (entry.timestamp == before.timestamp and seen <= before.seen)
            ):
                continue
            if not matches(entry, query):
                continue
            if len(entries) == query.limit:
                last = entries[-1]
                return LogPage(entries, LogCursor(last.timestamp, places[-1]))
            entries.append(entry)
            places.append(seen)
        return LogPage(entries, None)

    def entries(self, path: Path, before: LogCursor | None) -> Iterator[LogEntry]:
        """The entries of a file and of its rotated copies, the newest first. Every file is
        opened first, so that a rotation while they are read neither loses nor repeats one."""
        with contextlib.ExitStack() as stack:
            files: list[BinaryIO] = []
            inodes: set[tuple[int, int]] = set()
            for candidate in rotated(path):
                try:
                    opened = stack.enter_context(candidate.open("rb"))
                except FileNotFoundError:
                    break
                status = os.fstat(opened.fileno())
                if (status.st_dev, status.st_ino) not in inodes:
                    inodes.add((status.st_dev, status.st_ino))
                    files.append(opened)
            for file in files:
                if before is not None:
                    first = first_timestamp(file)
                    # Every entry of this file is newer than the page asked.
                    if first is not None and first > before.timestamp:
                        continue
                for line in lines_backwards(file):
                    entry = entry_of(line)
                    if entry is not None:
                        yield entry


def rotated(path: Path) -> Iterator[Path]:
    """`api.jsonl`, then `api.jsonl.1`, `api.jsonl.2`... as RotatingFileHandler names them."""
    yield path
    number = 1
    while True:
        yield path.with_name(f"{path.name}.{number}")
        number += 1
