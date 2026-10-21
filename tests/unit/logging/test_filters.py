import logging

from shelfdrop.logging.context import request_id_var
from shelfdrop.logging.filters import RequestIdFilter

UVICORN_LOGGER = "uvicorn.error"
REFUSED_MESSAGE = "ASGI callable returned without completing handshake."
OTHER_MESSAGE = "connection rejected (401 Unauthorized)"


def test_adds_the_current_request_id() -> None:
    record = logging.makeLogRecord({})
    token = request_id_var.set("req-1")
    try:
        kept = RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)

    assert kept is True
    assert vars(record)["request_id"] == "req-1"


def test_leaves_records_outside_requests_untouched() -> None:
    record = logging.makeLogRecord({})

    assert RequestIdFilter().filter(record) is True
    assert "request_id" not in vars(record)
