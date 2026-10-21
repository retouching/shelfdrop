import json
import logging
import sys
from pathlib import PurePosixPath

from shelfdrop.logging.formatters import JsonFormatter


def new_record(**attributes: object) -> logging.LogRecord:
    base: dict[str, object] = {
        "name": "shelfdrop.tests",
        "levelno": logging.INFO,
        "levelname": "INFO",
        "msg": "hello %s",
        "args": ("world",),
        "created": 0.0,
    }
    return logging.makeLogRecord({**base, **attributes})


def test_formats_one_line_with_the_base_fields() -> None:
    output = JsonFormatter().format(new_record(request_id="req-1"))

    assert "\n" not in output
    assert json.loads(output) == {
        "timestamp": "1970-01-01T00:00:00.000+00:00",
        "level": "INFO",
        "logger": "shelfdrop.tests",
        "message": "hello world",
        "request_id": "req-1",
    }


def test_request_id_is_null_outside_requests() -> None:
    assert json.loads(JsonFormatter().format(new_record()))["request_id"] is None


def test_keeps_extra_fields_but_not_uvicorn_colors_nor_overrides() -> None:
    record = new_record(status=404, color_message="\x1b[36mhello\x1b[0m", level="spoofed")

    payload = json.loads(JsonFormatter().format(record))

    assert payload["status"] == 404
    assert payload["level"] == "INFO"
    assert "color_message" not in payload
    assert "pathname" not in payload
    assert "args" not in payload


def test_serializes_the_exception_traceback() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = new_record(exc_info=sys.exc_info())

    output = JsonFormatter().format(record)

    assert "\n" not in output
    exception = json.loads(output)["exception"]
    assert exception.startswith("Traceback (most recent call last):")
    assert exception.endswith("ValueError: boom")


def test_non_json_values_are_written_as_strings() -> None:
    record = new_record(target=PurePosixPath("/srv/data"))

    assert json.loads(JsonFormatter().format(record))["target"] == "/srv/data"
