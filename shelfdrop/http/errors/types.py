"""Error codes of every error response body (each member's comment is its documentation) and
FieldError, one entry of a 422."""

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable values clients may branch on: adding one is additive, changing one is breaking."""

    # 404: no route for the path.
    NOT_FOUND = "not_found"
    # 404: no work with this id in the cache: unknown, or its search is older than 7 days;
    # data = null.
    WORK_NOT_FOUND = "work_not_found"
    # 404: no release search with this id: unknown, or finished more than 10 minutes ago;
    # data = null.
    SEARCH_NOT_FOUND = "search_not_found"
    # 405: the path exists, the method does not; the Allow header lists the methods.
    METHOD_NOT_ALLOWED = "method_not_allowed"
    # Any other HTTP error raised by the framework itself, with its own status.
    HTTP_ERROR = "http_error"
    # 422: the request does not match the schema; data = {"errors": [{"type", "loc", "msg"}]},
    # never the values sent.
    VALIDATION_FAILED = "validation_failed"
    # 422: the search has fewer than 2 letters or digits once normalized; data = null.
    QUERY_TOO_SHORT = "query_too_short"
    # 422: a search of a work under more names than allowed (6); data = null.
    TOO_MANY_NAMES = "too_many_names"
    # 422: a filter rule whose words or regular expression are empty or invalid;
    # data = {"positions": [index of each such rule in the list sent]}.
    INVALID_FILTER_RULE = "invalid_filter_rule"
    # 503: Prowlarr does not answer, answers an error, or its address or key is not set;
    # data = null.
    PROWLARR_UNAVAILABLE = "prowlarr_unavailable"
    # 503: none of the metadata sources of the kind answered (down, timed out, or skipped
    # because it failed less than 5 minutes ago); data = null.
    SOURCES_UNAVAILABLE = "sources_unavailable"
    # 500: unexpected error; the details stay in the logs.
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class FieldError:
    """One entry of a 422 validation_failed: where, what and which rule (never the input)."""

    loc: tuple[str | int, ...]
    msg: str
    type: str
