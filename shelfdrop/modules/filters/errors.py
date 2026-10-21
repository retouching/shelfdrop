"""HTTP errors of the filters module."""

from shelfdrop.http.errors.errors import unprocessable_with
from shelfdrop.http.errors.exceptions import ApiError
from shelfdrop.http.errors.types import ErrorCode


def invalid_filter_rule(positions: list[int]) -> ApiError:
    return unprocessable_with(
        ErrorCode.INVALID_FILTER_RULE,
        "A filter rule is empty or its expression is invalid",
        {"positions": positions},
    )
