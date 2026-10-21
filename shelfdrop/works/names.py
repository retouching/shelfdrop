"""Rules on the names of a work and of its authors: what makes a name specific, the key two
names are compared by, the order of a person's names."""

import re
from typing import Final

from shelfdrop.utils.text import normalize, words

# Words that never make a name or a release title specific.
STOPWORDS: Final = frozenset(
    [
        "the",
        "a",
        "an",
        "of",
        "and",
        "to",
        "in",
        "on",
        "le",
        "la",
        "les",
        "l",
        "de",
        "du",
        "des",
        "d",
        "et",
        "un",
        "une",
        "no",
        "wa",
        "ga",
        "ni",
        "to",
        "wo",
    ]
)


def significant_words(text: str) -> list[str]:
    """Words of 3 letters or more, without stop words: what a release title must contain."""
    return [w for w in words(text) if len(w) >= 3 and w not in STOPWORDS]


def is_abbreviation(text: str) -> bool:
    """'CSM', 'MDUD': short names that match too many unrelated releases."""
    compact = normalize(text).replace(" ", "")
    return len(compact) < 4 or (" " not in text.strip() and text.isupper() and len(compact) <= 5)


def person_name(raw: str) -> str:
    """'FUJIMOTO Tatsuki' (family name in capitals first) to 'Tatsuki Fujimoto'; 'Goggins, David'
    to 'David Goggins'; anything else unchanged but trimmed."""
    raw = " ".join(raw.split())
    if "," in raw:
        family, _, given = raw.partition(",")
        given = re.sub(r"\(.*?\)|\d{4}-?(\d{4})?", "", given).strip(" .")
        return f"{given} {family.strip()}".strip() if given else family.strip()
    parts = raw.split(" ")
    if len(parts) >= 2 and parts[0].isupper() and len(parts[0]) > 1 and not parts[1].isupper():
        return " ".join([*parts[1:], parts[0].capitalize()])
    return raw


def surname(name: str) -> str:
    parts = words(name)
    return parts[-1] if parts else ""


ARTICLE: Final = re.compile(r"^(the|a|an|le|la|les|l|un|une) ")


def match_key(text: str) -> str:
    """Key of a name for the merge: normalized, without a leading article ("The Bone Season" and
    "Bone season" are the same)."""
    return ARTICLE.sub("", normalize(text))
