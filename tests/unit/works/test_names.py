"""shelfdrop.works.names."""

import pytest

from shelfdrop.works.names import is_abbreviation, match_key, person_name, significant_words


def test_match_key_drops_leading_article() -> None:
    assert match_key("The Bone Season") == match_key("Bone season")
    assert match_key("L'atelier des sorciers") == "atelier des sorciers"


def test_significant_words() -> None:
    assert significant_words("Dusk Maiden of Amnesia") == ["dusk", "maiden", "amnesia"]


def test_abbreviations() -> None:
    assert is_abbreviation("CSM")
    assert is_abbreviation("MDUD")
    assert not is_abbreviation("Berserk")
    assert not is_abbreviation("Look Back")


@pytest.mark.parametrize(
    ("raw", "name"),
    [
        ("FUJIMOTO Tatsuki", "Tatsuki Fujimoto"),
        ("Goggins, David", "David Goggins"),
        ("Ushio, Kensuke (1983-....)", "Kensuke Ushio"),
        ("Samantha Shannon", "Samantha Shannon"),
    ],
)
def test_person_name(raw: str, name: str) -> None:
    assert person_name(raw) == name
