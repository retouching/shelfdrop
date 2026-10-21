"""Generic HTTP error factories: status, code, detail, data and headers of each."""

from shelfdrop.http.errors.errors import (
    not_found,
    unavailable,
    unprocessable,
    validation_failed,
)
from shelfdrop.http.errors.types import ErrorCode, FieldError


def test_not_found() -> None:
    error = not_found(ErrorCode.WORK_NOT_FOUND, "x")

    assert error.status_code == 404
    assert error.code == ErrorCode.WORK_NOT_FOUND
    assert error.detail == "x"
    assert error.data is None
    assert error.headers is None


def test_unprocessable() -> None:
    error = unprocessable(ErrorCode.VALIDATION_FAILED, "x")

    assert error.status_code == 422
    assert error.code == ErrorCode.VALIDATION_FAILED
    assert error.detail == "x"
    assert error.data is None
    assert error.headers is None


def test_unavailable() -> None:
    error = unavailable(ErrorCode.SOURCES_UNAVAILABLE, "x")

    assert error.status_code == 503
    assert error.code == ErrorCode.SOURCES_UNAVAILABLE
    assert error.detail == "x"
    assert error.data is None
    assert error.headers is None


def test_validation_failed_lists_the_field_errors() -> None:
    error = validation_failed(
        [
            FieldError(loc=("query", "q"), msg="m", type="value_error"),
            FieldError(loc=("query", "kind", 0), msg="n", type="missing"),
        ]
    )

    assert error.status_code == 422
    assert error.code == ErrorCode.VALIDATION_FAILED
    assert error.detail == "Request validation failed"
    assert error.data == {
        "errors": [
            {"type": "value_error", "loc": ["query", "q"], "msg": "m"},
            {"type": "missing", "loc": ["query", "kind", 0], "msg": "n"},
        ]
    }
    assert error.headers is None
