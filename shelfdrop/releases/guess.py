"""What a release title says: the volumes it holds, and whether it is the work of the name that
found it. And the text sent to Prowlarr for a name."""

import re
from typing import Final

from shelfdrop.releases.types import Volumes
from shelfdrop.utils.text import words
from shelfdrop.works.names import significant_words

# Characters some trackers fail on: they go from a query; the multiplication sign becomes "x".
UNSAFE: Final = re.compile(r"[:!?\"“”«»]")
MAX_VOLUME: Final = 999

# A pack: "T01-T11", "T01 à T11", "Tomes 1 à 3", "Vol.01-05", "v01-v05", Nyaa's "(01-23)".
RANGES: Final = (
    re.compile(
        r"(?<![A-Za-z0-9])T(?:omes?)?\.?\s?(\d{1,3})\s?(?:-|\u2013|à|a|to|~)\s?(?:T(?:ome)?\.?\s?)?(\d{1,3})(?![0-9])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z0-9])(?:Vol(?:ume)?s?\.?|v)\s?(\d{1,3})\s?(?:-|\u2013|à|to|~)\s?(?:(?:Vol(?:ume)?\.?|v)\s?)?(\d{1,3})(?![0-9])",
        re.IGNORECASE,
    ),
    re.compile(r"[(\[](\d{1,3})\s?-\s?(\d{1,3})[)\]]"),
)
# One volume: "T25", "T.25", "Tome 1", "Vol.01", "Volume 3", "v07".
SINGLES: Final = (
    re.compile(r"(?<![A-Za-z0-9])T(?:ome)?\.?\s?(\d{1,3})(?![0-9])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])(?:Vol(?:ume)?\.?|v)\s?(\d{1,3})(?![0-9])", re.IGNORECASE),
)
COMPLETE: Final = re.compile(
    r"(?<![A-Za-z])(INT[ÉE]GRALE|Complete|Complet|Collection\s+compl[eè]te)(?![A-Za-z])",
    re.IGNORECASE,
)


def volumes_of(title: str) -> Volumes:
    """'Jujutsu.Kaisen.T25.FRENCH...' -> T25; 'Demon Slayer (01-23) (Gotoge)' -> T01 to T23;
    '[INTEGRALE]' -> every volume; nothing recognized -> unknown."""
    text = title.replace("_", " ")
    for pattern in RANGES:
        found = pattern.search(text)
        if found:
            first, last = int(found.group(1)), int(found.group(2))
            if first < last <= MAX_VOLUME:
                return Volumes(kind="range", first=first, last=last)
            if first == last:
                return Volumes(kind="single", first=first, last=first)
    if COMPLETE.search(text):
        return Volumes(kind="complete")
    for pattern in SINGLES:
        found = pattern.search(text)
        if found:
            number = int(found.group(1))
            return Volumes(kind="single", first=number, last=number)
    return Volumes(kind="unknown")


def clean_query(text: str) -> str:
    """The text sent to Prowlarr: without `: ! ?` nor quotes, which break the search of some
    trackers, the multiplication sign as "x", the spaces collapsed."""
    text = UNSAFE.sub(" ", text.replace("\u00d7", "x"))
    return " ".join(text.split())


def is_relevant(title: str, name: str) -> bool:
    """A release is kept when its title holds every significant word of the name that found it
    (3 letters or more, stop words aside): "Amnesia T01" is not "Tasogare Otome x Amnesia"."""
    have = set(words(title))
    return all(word in have for word in significant_words(name))
