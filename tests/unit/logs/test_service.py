"""shelfdrop.logs.service: the files of logs read from their end, filtered, page by page."""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import pytest

from shelfdrop.logs import service
from shelfdrop.logs.service import LogReader, lines_backwards
from shelfdrop.logs.types import LogCursor, LogPage, LogProcess, LogQuery


def record(second: int, message: str, level: str = "INFO", **extra: object) -> str:
    return json.dumps(
        {
            "timestamp": f"2026-10-24T10:00:{second:02d}.000+00:00",
            "level": level,
            "logger": "shelfdrop.tests",
            "message": message,
            "request_id": None,
            **extra,
        }
    )


def write(path: Path, *lines: str) -> None:
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def reader_on(directory: Path) -> LogReader:
    return LogReader({process: directory / f"{process}.jsonl" for process in LogProcess})


def query(
    *,
    level: str = "DEBUG",
    text: str | None = None,
    limit: int = 200,
    before: LogCursor | None = None,
    process: LogProcess = LogProcess.API,
) -> LogQuery:
    return LogQuery(process, level, text, limit, before)


def messages(page: LogPage) -> list[str]:
    return [entry.message for entry in page.entries]


def test_the_entries_come_the_newest_first_with_their_fields(tmp_path: Path) -> None:
    write(
        tmp_path / "api.jsonl",
        record(1, "first"),
        record(2, "second", path="/api/v1/works", status=200, request_id="r-1"),
    )

    page = reader_on(tmp_path).read(query())

    assert messages(page) == ["second", "first"]
    assert page.entries[0].request_id == "r-1"
    assert page.entries[0].fields == {"path": "/api/v1/works", "status": 200}
    assert page.next is None


def test_a_process_reads_its_own_file_and_one_never_written_has_none(tmp_path: Path) -> None:
    write(tmp_path / "placement.jsonl", record(1, "Placement worker started"))

    assert messages(reader_on(tmp_path).read(query(process=LogProcess.PLACEMENT))) == [
        "Placement worker started"
    ]
    assert reader_on(tmp_path).read(query()).entries == []


def test_a_line_cut_or_foreign_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "api.jsonl").write_text(
        f'not json\n[1, 2]\n{record(1, "kept")}\n{{"timestamp": "2026', encoding="utf-8"
    )

    assert messages(reader_on(tmp_path).read(query())) == ["kept"]


def test_the_level_is_a_minimum(tmp_path: Path) -> None:
    write(
        tmp_path / "api.jsonl",
        record(1, "debug", "DEBUG"),
        record(2, "info"),
        record(3, "warning", "WARNING"),
        record(4, "error", "ERROR"),
    )

    assert messages(reader_on(tmp_path).read(query(level="WARNING"))) == ["error", "warning"]


def test_the_text_is_searched_without_case_in_every_field(tmp_path: Path) -> None:
    write(
        tmp_path / "api.jsonl",
        record(1, "Metadata source unavailable", source="anilist"),
        record(2, "GET /api/v1/works 200", request_id="req-42"),
        record(3, "Settings imported"),
    )
    reader = reader_on(tmp_path)

    assert messages(reader.read(query(text="ANILIST"))) == ["Metadata source unavailable"]
    assert messages(reader.read(query(text="req-42"))) == ["GET /api/v1/works 200"]
    assert messages(reader.read(query(text="imported"))) == ["Settings imported"]


def test_the_pages_go_through_the_rotated_files(tmp_path: Path) -> None:
    write(tmp_path / "api.jsonl.2", record(1, "a"), record(2, "b"))
    write(tmp_path / "api.jsonl.1", record(3, "c"), record(4, "d"))
    write(tmp_path / "api.jsonl", record(5, "e"))
    reader = reader_on(tmp_path)

    first = reader.read(query(limit=2))
    second = reader.read(query(limit=2, before=first.next))
    third = reader.read(query(limit=2, before=second.next))

    assert messages(first) == ["e", "d"]
    assert first.next == LogCursor("2026-10-24T10:00:04.000+00:00", 1)
    assert messages(second) == ["c", "b"]
    assert messages(third) == ["a"]
    assert third.next is None


def test_a_page_never_cuts_the_entries_of_one_millisecond(tmp_path: Path) -> None:
    write(tmp_path / "api.jsonl", *(record(1, f"same {n}") for n in range(5)), record(2, "later"))
    reader = reader_on(tmp_path)

    first = reader.read(query(limit=3))
    second = reader.read(query(limit=3, before=first.next))

    assert messages(first) == ["later", "same 4", "same 3"]
    assert first.next == LogCursor("2026-10-24T10:00:01.000+00:00", 2)
    assert messages(second) == ["same 2", "same 1", "same 0"]
    assert second.next is None


def test_the_filters_hold_from_page_to_page(tmp_path: Path) -> None:
    write(
        tmp_path / "api.jsonl",
        *(
            record(n, f"{'error' if n % 2 else 'info'} {n}", "ERROR" if n % 2 else "INFO")
            for n in range(1, 9)
        ),
    )
    reader = reader_on(tmp_path)

    first = reader.read(query(level="ERROR", limit=2))
    second = reader.read(query(level="ERROR", limit=2, before=first.next))

    assert messages(first) == ["error 7", "error 5"]
    assert messages(second) == ["error 3", "error 1"]


def test_a_file_newer_than_the_page_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(tmp_path / "api.jsonl", record(5, "e"), record(6, "f"))
    write(tmp_path / "api.jsonl.1", record(1, "a"), record(2, "b"))
    read: list[str] = []
    real = service.lines_backwards

    def counted(file: BinaryIO) -> Iterator[bytes]:
        read.append(file.name)
        return real(file)

    monkeypatch.setattr(service, "lines_backwards", counted)

    page = reader_on(tmp_path).read(query(before=LogCursor("2026-10-24T10:00:03.000+00:00", 1)))

    assert messages(page) == ["b", "a"]
    assert read == [str(tmp_path / "api.jsonl.1")]


def test_a_file_found_twice_during_a_rotation_is_read_once(tmp_path: Path) -> None:
    write(tmp_path / "api.jsonl", record(1, "once"))
    os.link(tmp_path / "api.jsonl", tmp_path / "api.jsonl.1")

    assert messages(reader_on(tmp_path).read(query())) == ["once"]


def test_lines_backwards_crosses_the_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "BLOCK_BYTES", 7)
    path = tmp_path / "lines"
    path.write_bytes(b"alpha\nbravo charlie\n\ndelta\nlast without end")

    with path.open("rb") as file:
        assert list(lines_backwards(file)) == [
            b"last without end",
            b"delta",
            b"bravo charlie",
            b"alpha",
        ]
