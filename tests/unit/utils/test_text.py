"""shelfdrop.utils.text."""

import pytest

from shelfdrop.utils.text import compact, normalize, script_of


def test_normalize() -> None:
    assert normalize("Tasogare Otome × Amnesia") == "tasogare otome x amnesia"
    assert normalize("L'Atelier des Sorciers !") == "l atelier des sorciers"
    assert normalize("Mémoire des os") == "memoire des os"


def test_compact() -> None:
    assert compact("Chain saw man") == compact("Chainsawman") == compact("Chainsaw Man")


@pytest.mark.parametrize(
    ("text", "script"),
    [
        ("チェンソーマン", "ja"),
        ("电锯人", "zh"),
        ("체인쏘맨", "ko"),
        ("Людина", "ru"),
        ("Berserk", "latin"),
    ],
)
def test_script_of(text: str, script: str) -> None:
    assert script_of(text) == script
