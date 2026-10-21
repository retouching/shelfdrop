"""shelfdrop.utils.text."""

import pytest

from shelfdrop.utils.text import compact, normalize, plain, script_of


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


def test_a_summary_loses_its_markup_and_keeps_its_paragraphs() -> None:
    assert (
        plain("Guts&#039;s <b>sword</b><br />  <br><br>next   line") == "Guts's sword\n\nnext line"
    )
    assert plain("x" * 10, limit=4) == "xxxx"
