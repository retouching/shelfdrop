"""Generic ISBN helpers."""

import re
from typing import Final

ISBN_CHARS: Final = re.compile(r"[\s-]")


def parse_isbn(text: str) -> str | None:
    """The ISBN-13 or ISBN-10 the text is, if it is one (dashes and spaces allowed)."""
    candidate = ISBN_CHARS.sub("", text.strip()).upper()
    if len(candidate) == 13 and candidate.isdigit():
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(candidate[:12]))
        return candidate if (10 - total % 10) % 10 == int(candidate[12]) else None
    if (
        len(candidate) == 10
        and candidate[:9].isdigit()
        and (candidate[9].isdigit() or candidate[9] == "X")
    ):
        total = sum(int(d) * (10 - i) for i, d in enumerate(candidate[:9]))
        check = 10 if candidate[9] == "X" else int(candidate[9])
        return candidate if (total + check) % 11 == 0 else None
    return None


def isbn13_of(isbn: str) -> str:
    """ISBN-10 to ISBN-13, so both forms of the same book compare equal."""
    if len(isbn) == 13:
        return isbn
    body = "978" + isbn[:9]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)
