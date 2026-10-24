"""shelfdrop.modules.logs.router: the records of a file of logs, page by page, for a session."""

import json
from pathlib import Path

import pytest

from shelfdrop.config import Settings
from tests.unit.test_main import client_for, settings_for


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def write_logs(settings: Settings, name: str, *messages: str) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    lines = (
        json.dumps(
            {
                "timestamp": f"2026-10-24T10:00:{n:02d}.000+00:00",
                "level": "ERROR" if message.startswith("!") else "INFO",
                "logger": "shelfdrop.tests",
                "message": message,
                "request_id": f"req-{n}",
                "status": 200,
            }
        )
        for n, message in enumerate(messages)
    )
    (settings.log_dir / name).write_text("".join(f"{line}\n" for line in lines), "utf-8")


@pytest.mark.anyio
async def test_the_entries_come_with_their_fields_and_the_cursor_of_the_older(
    tmp_path: Path,
) -> None:
    settings = settings_for(tmp_path)
    write_logs(settings, "api.jsonl", "a", "b", "c")
    async with client_for(settings) as client:
        first = await client.get("/api/v1/logs", params={"limit": 2})
        older = await client.get(
            "/api/v1/logs", params={"limit": 2, "before": first.json()["next"]}
        )

    assert first.status_code == 200
    body = first.json()
    assert body["entries"][0] == {
        "timestamp": "2026-10-24T10:00:02.000+00:00",
        "level": "INFO",
        "logger": "shelfdrop.tests",
        "message": "c",
        "request_id": "req-2",
        "fields": {"status": 200},
    }
    assert [e["message"] for e in body["entries"]] == ["c", "b"]
    assert body["next"] == "2026-10-24T10:00:01.000+00:00~1"
    assert older.json() == {
        "entries": [
            {
                "timestamp": "2026-10-24T10:00:00.000+00:00",
                "level": "INFO",
                "logger": "shelfdrop.tests",
                "message": "a",
                "request_id": "req-0",
                "fields": {"status": 200},
            }
        ],
        "next": None,
    }


@pytest.mark.anyio
async def test_the_service_the_level_and_the_text_filter(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    write_logs(settings, "api.jsonl", "api")
    write_logs(settings, "placement.jsonl", "placed", "!failed", "!other")
    async with client_for(settings) as client:
        response = await client.get(
            "/api/v1/logs", params={"service": "placement", "level": "ERROR", "text": "FAIL"}
        )

    assert [e["message"] for e in response.json()["entries"]] == ["!failed"]


@pytest.mark.anyio
async def test_no_file_yet_is_no_entry(tmp_path: Path) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.get("/api/v1/logs", params={"service": "placement"})

    assert response.json() == {"entries": [], "next": None}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {"limit": "0"},
        {"limit": "1001"},
        {"service": "jellyfin"},
        {"level": "TRACE"},
        {"before": "yesterday"},
        {"before": "2026-10-24T10:00:01.000+00:00~0"},
    ],
)
async def test_a_wrong_parameter_is_a_422(tmp_path: Path, params: dict[str, str]) -> None:
    async with client_for(settings_for(tmp_path)) as client:
        response = await client.get("/api/v1/logs", params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
