"""Exceptions of the downloads."""


class UnknownReleasesError(Exception):
    """Releases the search does not hold, or without a download link; `ids` lists them."""

    def __init__(self, ids: list[str]) -> None:
        super().__init__("releases not in the search")
        self.ids = ids


class NotAutomaticError(Exception):
    """Releases an automatic download may not take: set aside by the filters, or from a
    tracker not allowed for the automatic downloads; `ids` lists them."""

    def __init__(self, ids: list[str]) -> None:
        super().__init__("releases not automatic")
        self.ids = ids


class DownloadNotFoundError(Exception):
    """No download with this id."""


class NotRetryableError(Exception):
    """A download that is not a failed send: only a torrent qBittorrent did not receive is sent
    again (a duplicate never is)."""
