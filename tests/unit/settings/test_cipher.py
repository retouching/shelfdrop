"""shelfdrop.settings.cipher: AES-GCM, the name bound to the value."""

import pytest

from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.exceptions import SecretUnreadableError
from tests.unit.settings.support import TEST_SECRET_KEY


def test_a_sealed_secret_opens_under_its_name() -> None:
    box = SecretBox(TEST_SECRET_KEY)

    sealed = box.seal("prowlarr.api_key", "abc123")

    assert b"abc123" not in sealed
    assert box.open("prowlarr.api_key", sealed) == "abc123"


def test_two_seals_of_one_value_differ() -> None:
    box = SecretBox(TEST_SECRET_KEY)

    assert box.seal("k", "abc123") != box.seal("k", "abc123")


@pytest.mark.parametrize(
    ("key", "name", "change"),
    [
        ("x" * 32, "prowlarr.api_key", False),
        (TEST_SECRET_KEY, "jellyfin.api_key", False),
        (TEST_SECRET_KEY, "prowlarr.api_key", True),
    ],
)
def test_another_key_another_name_or_a_change_cannot_open(
    key: str, name: str, change: bool
) -> None:
    sealed = bytearray(SecretBox(TEST_SECRET_KEY).seal("prowlarr.api_key", "abc123"))
    if change:
        sealed[-1] ^= 1

    with pytest.raises(SecretUnreadableError):
        SecretBox(key).open(name, bytes(sealed))
