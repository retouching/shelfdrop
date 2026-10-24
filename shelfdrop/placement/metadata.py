"""The metadata Jellyfin keeps of a file placed: its name, its series, its number and its
authors set from the shelf, and locked. Pure: no I/O."""

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any, Final

from shelfdrop.placement.naming import chapter_sort_name
from shelfdrop.placement.types import ShelfFile

# The fields of `MetadataField` a placement locks: its name, its people.
LOCKED: Final = ("Name", "Cast")


def authors_of(author: str) -> list[str]:
    return [name.strip() for name in author.split(",") if name.strip()]


def locked_item(
    body: dict[str, Any], placed: ShelfFile, volumes: Sequence[int], *, forced: bool = False
) -> dict[str, Any]:
    """The whole item `body` (`GET /Items/{id}`) with the name of its file, its series, its
    number, its authors (when it has none) and its sort, and those fields locked; `volumes`:
    the volumes of its series on the shelf, before which a chapter alone sorts. `forced` (the
    sync asked from the page Jellyfin): the authors of the shelf replace those of the item, its
    other people kept. Its images are never touched."""
    item = dict(body)
    name = PurePosixPath(placed.path).stem
    item["Name"] = name
    item["SeriesName"] = placed.series
    if placed.chapter is None:
        item["SortName"] = item["ForcedSortName"] = name
        if placed.volume is not None:
            item["IndexNumber"] = placed.volume
    else:
        before = [v for v in volumes if placed.volume is None or v < placed.volume]
        after = max(before, default=None)
        item["SortName"] = item["ForcedSortName"] = chapter_sort_name(
            placed.series, after, placed.chapter
        )
    authors = [{"Name": name, "Type": "Author", "Role": ""} for name in authors_of(placed.author)]
    if forced and authors:
        others = [
            p for p in item.get("People") or [] if isinstance(p, dict) and p.get("Type") != "Author"
        ]
        item["People"] = [*authors, *others]
    elif not item.get("People") and authors:
        item["People"] = authors
    locked = set(item.get("LockedFields") or []) | set(LOCKED)
    item["LockedFields"] = sorted(locked)
    return item
