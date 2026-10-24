"""Exceptions of the release search."""


class ProwlarrError(Exception):
    """Prowlarr did not answer, or answered an error; the message names a status or a class,
    `status` is the HTTP status of an answer."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ProwlarrNotConfiguredError(ProwlarrError):
    """No address or no key of Prowlarr in the settings."""


class SearchNotFoundError(Exception):
    """No search with this id: unknown, or finished too long ago."""


class ReleaseNotFoundError(Exception):
    """No release with this id in the searches kept, or one without a download link."""


class TooManyNamesError(Exception):
    """More names than a work search may send to Prowlarr."""


class InvalidRuleError(Exception):
    """A filter rule whose expression is empty or invalid; `positions` lists them."""

    def __init__(self, positions: list[int]) -> None:
        super().__init__("invalid filter rules")
        self.positions = positions


class UnknownCategoryError(Exception):
    """Categories chosen for a tracker that it does not know; `indexer_ids` lists them."""

    def __init__(self, indexer_ids: list[int]) -> None:
        super().__init__("unknown categories")
        self.indexer_ids = indexer_ids
