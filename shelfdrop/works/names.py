"""Rules on the names of a work and of its authors: what makes a name specific, the key two
names are compared by, the order of a person's names."""

import re
from typing import Final

from shelfdrop.utils.text import normalize, script_of, words

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

# The language a source writes in brackets after a name: "Atelier of Witch Hat (Indonesian)".
TAGGED_LANGUAGES: Final = {
    "english": "en",
    "french": "fr",
    "romaji": "ja-ro",
    "indonesian": "id",
    "polish": "pl",
    "turkish": "tr",
    "spanish": "es",
    "portuguese": "pt",
    "italian": "it",
    "german": "de",
    "vietnamese": "vi",
    "malay": "ms",
    "czech": "cs",
    "russian": "ru",
    "thai": "th",
}
LANGUAGE_TAG: Final = re.compile(r"\((?P<tag>[A-Za-z ]+)\)\s*$")
# Letters only some languages use (French accents are shared, they decide nothing alone).
LETTERS: Final = (
    ("tr", frozenset("ıİşŞğĞ")),
    ("pl", frozenset("ąęłńśźżĄĘŁŃŚŹŻ")),
    ("cs", frozenset("ěřůĚŘŮ")),
    ("hu", frozenset("őűŐŰ")),
    ("ro", frozenset("ășțĂȘȚ")),
    ("vi", frozenset("ơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹđƠƯĐ")),
    ("es", frozenset("ñÑ¿¡")),
    ("pt", frozenset("ãõÃÕ")),
    ("de", frozenset("ßäÄ")),
)
# Small words that say the language of a title; the language with the most of them wins.
FUNCTION_WORDS_TEXT: Final = {
    "en": "the of and is are an my your his her with for from who what when this that be into",
    "fr": "le la les des du et un une au aux pour sur dans avec qui ne pas est",
    "es": "el los las del y con por una que se",
    "pt": "os da do das dos com uma",
    "it": "il gli della delle dello di per",
    "de": "der die das und ein eine mit von",
    "id": "yang dan dari dengan untuk dalam pada ingin",
    "tr": "ve bir ile",
    "nl": "het een van",
}
FUNCTION_WORDS: Final = {
    lang: frozenset(text.split()) for lang, text in FUNCTION_WORDS_TEXT.items()
}
# A word of Japanese written in Latin letters: a run of the syllables of Hepburn romanization.
ROMAJI_WORD: Final = re.compile(
    r"^(?:(?:[kgsztdnhbpmr]y?|ch|sh|ts|j|f|w|y)?[aeiou]|n|[kstpgdbz](?=[kstpgdbzc]))+$"
)
# What a romaji name shows: a particle, an honorific, a long vowel or a syllable English lacks.
ROMAJI_PARTICLES: Final = frozenset(("no", "wa", "ga", "wo", "ni", "to", "de", "mo", "ka"))
ROMAJI_SUFFIXES: Final = ("sama", "kun", "chan", "san", "sensei")
ROMAJI_SOUNDS: Final = re.compile(r"shi|chi|tsu|ky|ry|ny|ou|uu|oo|ei|fu|ji")
MACRONS: Final = frozenset("āīūēōâîûêô")


def is_romaji(title: str) -> bool:
    """'Tongari Boushi no Atelier' is not (Atelier), 'Tongari Booshi no Atorie' and 'Chensoo Man'
    are: every word is made of Japanese syllables, and one of them shows it."""
    found = [w for w in words(title) if len(w) > 1 and not w.isdigit()]
    if not found or not all(ROMAJI_WORD.match(w) for w in found):
        return False
    return (
        any(w in ROMAJI_PARTICLES or w.endswith(ROMAJI_SUFFIXES) for w in found)
        or any(c in MACRONS for c in title.lower())
        or any(ROMAJI_SOUNDS.search(w) for w in found)
    )


def language_of(title: str) -> str:
    """The language of a name a source gave without one, or 'latin' when it cannot be told.

    Prudent on purpose: only the names whose language is known are searched by default. A tag
    in brackets decides first, then the letters only one language uses, then romaji, then the
    small words of a language, when one language has more of them than any other.
    """
    script = script_of(title)
    if script != "latin":
        return script
    tag = LANGUAGE_TAG.search(title)
    if tag and tag.group("tag").strip().lower() in TAGGED_LANGUAGES:
        return TAGGED_LANGUAGES[tag.group("tag").strip().lower()]
    for language, letters in LETTERS:
        if any(c in letters for c in title):
            return language
    if is_romaji(title):
        return "ja-ro"
    found = words(title)
    counts = {lang: sum(w in small for w in found) for lang, small in FUNCTION_WORDS.items()}
    best = max(counts.values())
    winners = [lang for lang, count in counts.items() if count == best]
    return winners[0] if best and len(winners) == 1 else "latin"


def match_key(text: str) -> str:
    """Key of a name for the merge: normalized, without a leading article ("The Bone Season" and
    "Bone season" are the same)."""
    return ARTICLE.sub("", normalize(text))
