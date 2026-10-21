"""Exceptions of the work search."""


class SourceError(Exception):
    """A metadata source did not answer usefully: down, timed out, or an unexpected body. Its
    message is a status or a class name, never an address nor a body."""


class QueryTooShortError(ValueError):
    """The search has fewer than 2 letters or digits once normalized."""


class NoSourceAnsweredError(Exception):
    """No metadata source of the kind answered."""


class WorkNotFoundError(Exception):
    """No work with this id in the cache."""
