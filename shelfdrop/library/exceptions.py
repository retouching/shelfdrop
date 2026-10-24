"""The exceptions of the page Jellyfin."""


class SeriesNotFoundError(Exception):
    """No series of a library of books of Jellyfin has this id."""


class LibraryUnavailableError(Exception):
    """Jellyfin does not answer, answers an error, or its address or its key is not set."""


class ImageRefusedError(Exception):
    """The image chosen is not a JPEG, a PNG or a WebP of 5 MB at most, or was not read."""


class AdoptionRefusedError(Exception):
    """An adoption the page cannot make: `reason` (`no_work`: the series has no work;
    `unknown`: a file that is no volume of the series; `adopted`: a file already on the shelf;
    `unnumbered`: a file without a volume nor a chapter; `duplicate`: two files, or a file and
    the shelf, of the same number), and the files it names."""

    def __init__(self, reason: str, item_ids: tuple[str, ...] = ()) -> None:
        super().__init__(reason)
        self.reason = reason
        self.item_ids = item_ids


class VolumeNotFoundError(Exception):
    """No book nor audiobook of a library of books of Jellyfin has this id."""
