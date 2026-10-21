"""The exceptions of the page Métadonnées."""


class SeriesNotFoundError(Exception):
    """No series of a library of books of Jellyfin has this id."""


class LibraryUnavailableError(Exception):
    """Jellyfin does not answer, answers an error, or its address or its key is not set."""


class ImageRefusedError(Exception):
    """The image chosen is not a JPEG, a PNG or a WebP of 5 MB at most, or was not read."""
