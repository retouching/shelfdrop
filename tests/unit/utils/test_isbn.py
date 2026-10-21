"""shelfdrop.utils.isbn."""

from shelfdrop.utils.isbn import isbn13_of, parse_isbn


def test_isbn() -> None:
    assert parse_isbn("978-2-37753-067-0") == "9782377530670"
    assert parse_isbn("2377530672") == "2377530672"
    assert parse_isbn("9782377530671") is None
    assert parse_isbn("Berserk") is None
    assert isbn13_of("2377530672") == "9782377530670"
