"""shelfdrop.utils.passwords: the scrypt of a password, its parameters and its salt with it."""

import pytest

from shelfdrop.utils.passwords import hash_password, verify_password


def test_a_password_gives_its_hash_again_and_no_other() -> None:
    stored = hash_password("correct horse battery")

    assert verify_password("correct horse battery", stored) is True
    assert verify_password("correct horse batterY", stored) is False
    assert "correct" not in stored


def test_the_parameters_and_a_random_salt_are_kept_with_the_hash() -> None:
    first, second = hash_password("same"), hash_password("same")

    assert first != second
    scheme, cost, block_size, parallelism, salt, digest = first.split("$")
    assert (scheme, cost, block_size, parallelism) == ("scrypt", "32768", "8", "1")
    assert len(salt) >= 21
    assert len(digest) >= 42


def test_a_hash_of_other_parameters_is_read_with_its_own() -> None:
    stored = hash_password("same")
    salt, digest = stored.split("$")[4:]

    assert verify_password("same", f"scrypt$16384$8$1${salt}${digest}") is False


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "bcrypt$2b$12$abc",
        "scrypt$32768$8$1$salt",
        "scrypt$x$8$1$c2FsdA$ZGlnZXN0",
        "scrypt$1000$8$1$c2FsdA$ZGlnZXN0",
        "scrypt$4194304$8$1$c2FsdA$ZGlnZXN0",
        "scrypt$32768$8$1$***$ZGlnZXN0",
    ],
)
def test_a_hash_it_cannot_read_matches_nothing(stored: str) -> None:
    assert verify_password("anything", stored) is False
