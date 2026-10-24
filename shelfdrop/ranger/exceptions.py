"""Exceptions of the page Ranger."""


class ItemNotFoundError(Exception):
    """No file of Ranger (or of the shelf) has this id."""


class ItemBusyError(Exception):
    """The file is placed, or the worker has a request of it to do already."""


class ItemNotIgnoredError(Exception):
    """The file taken back is not ignored."""


class RequestRefusedError(Exception):
    """The request does not fit the file: volumes of chapters for a file that is not a release
    in chapters, ranges of chapters that overlap."""
