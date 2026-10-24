"""Which releases answer a waiting search, and where a search of chapters stands once some are
placed. Pure: no I/O."""

from collections.abc import Collection, Iterable

from shelfdrop.releases.guess import chapters_of
from shelfdrop.releases.types import Release
from shelfdrop.waiting.types import Wanted


def holds_volume(release: Release, volume: int) -> bool:
    """A release that holds `volume`: that one, a pack around it, or a complete edition."""
    held = release.volumes
    match held.kind:
        case "single":
            return held.first == volume
        case "range":
            return (
                held.first is not None
                and held.last is not None
                and held.first <= volume <= held.last
            )
        case "complete":
            return True
        case "unknown":
            return False


def holds_chapters(release: Release, start: float, end: float | None) -> bool:
    """A release whose name states a chapter of `start` to `end` (every one after when None)."""
    chapters = chapters_of(release.title)
    if chapters is None:
        return False
    last = chapters.last if chapters.last is not None else chapters.first
    return last >= start and (end is None or chapters.first <= end)


def answers(wanted: Wanted, release: Release) -> bool:
    """A release kept by the filters (score, words, trackers) that holds what is waited for."""
    if release.rejected is not None:
        return False
    match wanted.target:
        case "any":
            return True
        case "volume":
            return wanted.volume is not None and holds_volume(release, wanted.volume)
        case "chapters":
            return wanted.chapter_from is not None and holds_chapters(
                release, wanted.chapter_from, wanted.chapter_to
            )


def found(wanted: Wanted, releases: Iterable[Release]) -> int:
    return sum(1 for r in releases if answers(wanted, r))


def next_chapter(start: float, placed: Collection[float]) -> float:
    """The first chapter from `start` not placed yet: 233 placed, 234 placed, 235 is next."""
    chapter = start
    while chapter in placed:
        chapter = float(int(chapter) + 1)
    return chapter


def is_done(wanted: Wanted, volumes: Collection[int], chapters: Collection[float]) -> bool:
    """A volume placed, or chapters placed past their end, leave the list; any release waits
    until removed."""
    match wanted.target:
        case "any":
            return False
        case "volume":
            return wanted.volume in volumes
        case "chapters":
            if wanted.chapter_from is None or wanted.chapter_to is None:
                return False
            return next_chapter(wanted.chapter_from, chapters) > wanted.chapter_to


def label(wanted: Wanted) -> str:
    """'T03', 'Ch. 233 et suivants', 'Ch. 233 à 240', 'Toute release': the label of the API, in
    French (the page and the journal write theirs in their own language)."""
    match wanted.target:
        case "any":
            return "Toute release"
        case "volume":
            return f"T{wanted.volume or 0:02d}"
        case "chapters":
            start = number_label(wanted.chapter_from or 0)
            if wanted.chapter_to is None:
                return f"Ch. {start} et suivants"
            return f"Ch. {start} \u00e0 {number_label(wanted.chapter_to)}"


def number_label(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)
