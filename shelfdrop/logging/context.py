"""Context variables read by the logging filters."""

from contextvars import ContextVar

# Set by shelfdrop.http.middleware.request_id for the duration of each HTTP request.
request_id_var: ContextVar[str | None] = ContextVar("shelfdrop_request_id", default=None)
