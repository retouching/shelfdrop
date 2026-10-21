import json
import logging
import re

import httpx
import pytest

from shelfdrop.logging.context import request_id_var
from shelfdrop.logging.setup import configure_logging

TEXT_LINE = r"\S+ \S+ WARNING shelfdrop\.tests\.text \[{request_id}\] {message}"


@pytest.mark.usefixtures("isolated_logging")
def test_existing_loggers_write_json_lines_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    existing = logging.getLogger("shelfdrop.tests.existing")

    configure_logging(level="INFO", json_format=True)
    existing.info("still enabled")
    logging.getLogger("uvicorn.error").info("from uvicorn")

    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [(record["logger"], record["message"]) for record in records] == [
        ("shelfdrop.tests.existing", "still enabled"),
        ("uvicorn.error", "from uvicorn"),
    ]


@pytest.mark.usefixtures("isolated_logging")
def test_level_filters_records(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="WARNING", json_format=True)
    logger = logging.getLogger("shelfdrop.tests.level")
    logger.info("dropped")
    logger.warning("kept")

    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [record["message"] for record in records] == ["kept"]


@pytest.mark.usefixtures("isolated_logging")
def test_text_format_shows_the_request_id_or_a_dash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="INFO", json_format=False)
    logger = logging.getLogger("shelfdrop.tests.text")
    logger.warning("outside")
    token = request_id_var.set("req-7")
    try:
        logger.warning("inside")
    finally:
        request_id_var.reset(token)

    outside, inside = capsys.readouterr().err.splitlines()
    assert re.fullmatch(TEXT_LINE.format(request_id="-", message="outside"), outside)
    assert re.fullmatch(TEXT_LINE.format(request_id="req-7", message="inside"), inside)


@pytest.mark.usefixtures("isolated_logging")
def test_uvicorn_access_log_is_disabled() -> None:
    logging.getLogger("uvicorn.access").addHandler(logging.StreamHandler())

    configure_logging(level="INFO", json_format=True)

    assert not logging.getLogger("uvicorn.access").hasHandlers()


@pytest.mark.parametrize(
    ("level", "warnings_enabled"), [("DEBUG", True), ("ERROR", False)], ids=["debug", "error"]
)
@pytest.mark.parametrize(
    "name",
    [
        "sqlalchemy.engine.Engine",
        "httpx",
        "httpcore.connection",
    ],
)
@pytest.mark.usefixtures("isolated_logging")
def test_sqlalchemy_and_httpx_never_log_below_warning(
    name: str, level: str, warnings_enabled: bool
) -> None:
    configure_logging(level=level, json_format=True)

    library_logger = logging.getLogger(name)
    assert not library_logger.isEnabledFor(logging.DEBUG)
    assert not library_logger.isEnabledFor(logging.INFO)
    assert library_logger.isEnabledFor(logging.WARNING) is warnings_enabled


@pytest.mark.usefixtures("isolated_logging")
def test_a_request_of_httpx_never_logs_its_address(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="DEBUG", json_format=True)

    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        client.post("https://discord.com/api/webhooks/1/leaky-token")

    assert "leaky-token" not in capsys.readouterr().err
