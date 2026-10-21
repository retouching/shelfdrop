"""Generic text helpers: comparison forms of a text and the script it is written in."""

import html
import re
import unicodedata
from typing import Final

SEPARATORS: Final = re.compile(r"[^0-9a-z]+")


def normalize(text: str) -> str:
    """Lower case, no accents, the multiplication sign as 'x', and every run of punctuation or
    space as one space."""
    text = text.replace("\u00d7", "x").replace("\u2019", "'")  # multiplication sign, curly quote
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return SEPARATORS.sub(" ", stripped.lower()).strip()


def words(text: str) -> list[str]:
    return [w for w in normalize(text).split() if w]


def script_of(text: str) -> str:
    """'latin', 'ja', 'ko', 'zh', 'ru', 'ar', 'other' from the letters of the text."""
    counts: dict[str, int] = {}
    for char in text:
        if not char.isalpha():
            continue
        name = unicodedata.name(char, "")
        if name.startswith(("HIRAGANA", "KATAKANA")):
            script = "ja"
        elif name.startswith("CJK"):
            script = "zh"
        elif name.startswith("HANGUL"):
            script = "ko"
        elif name.startswith("CYRILLIC"):
            script = "ru"
        elif name.startswith("ARABIC"):
            script = "ar"
        elif name.startswith("LATIN"):
            script = "latin"
        else:
            script = "other"
        counts[script] = counts.get(script, 0) + 1
    if not counts:
        return "latin"
    if counts.get("ja"):
        return "ja"  # kana with kanji: Japanese, not Chinese
    return max(counts, key=lambda k: counts[k])


def is_latin(text: str) -> bool:
    return script_of(text) == "latin"


def compact(text: str) -> str:
    """'Chain saw man', 'Chainsawman' and 'Chainsaw Man' give the same compact form."""
    return normalize(text).replace(" ", "")


def plain(text: str, limit: int = 4000) -> str:
    """A summary without its markup: tags removed, entities read, blank lines kept single,
    spaces reduced, `limit` characters at most."""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    joined = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", joined).strip()[:limit]
