"""The libraries as Jellyfin sees them and as the placement sees them: a library of Jellyfin is
the one of a kind when one of its folders has the name of the folder of the kind
(`/files/comics` in Jellyfin, `/data/files/comics` here). Pure: no I/O."""

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Final

from shelfdrop.clients.types import JellyfinLibrary
from shelfdrop.placement.types import LIBRARY_NAMES
from shelfdrop.works.types import Kind

# Between the library and the series: a single right-pointing angle quotation mark.
SEPARATOR: Final = " \u203a "


def library_of(root: str, libraries: Sequence[JellyfinLibrary]) -> tuple[JellyfinLibrary, str]:
    """The library of Jellyfin of the folder `root` and the folder of it that matches; raises
    LookupError without one."""
    name = PurePosixPath(root).name
    for library in libraries:
        for location in library.locations:
            if PurePosixPath(location).name == name:
                return library, location
    raise LookupError(root)


def to_jellyfin(path: str, root: str, location: str) -> str:
    """`/data/files/comics/Berserk/x.cbz` as Jellyfin sees it: `/files/comics/Berserk/x.cbz`."""
    return str(PurePosixPath(location) / PurePosixPath(path).relative_to(root))


def to_local(path: str, roots: Mapping[Kind, str], libraries: Sequence[JellyfinLibrary]) -> str:
    """A path of Jellyfin as the placement sees it; raises LookupError when it is in no library
    of a kind, or leaves it (`..`)."""
    seen = PurePosixPath(path)
    if ".." in seen.parts:
        raise LookupError(path)
    for root in roots.values():
        try:
            _, location = library_of(root, libraries)
        except LookupError:
            continue
        if seen.is_relative_to(location):
            return str(PurePosixPath(root) / seen.relative_to(location))
    raise LookupError(path)


def destination_label(kind: Kind, series: str, library: JellyfinLibrary | None) -> str:
    """The name of the library in Jellyfin (or of its kind), then the series, as the page and
    the journal show them ('BD & Mangas', the separator, 'Chainsaw Man')."""
    name = library.name if library is not None else LIBRARY_NAMES[kind]
    return f"{name}{SEPARATOR}{series}"
