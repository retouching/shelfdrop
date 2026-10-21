"""shelfdrop.works.names."""

import pytest

from shelfdrop.works.names import (
    is_abbreviation,
    is_romaji,
    language_of,
    match_key,
    person_name,
    significant_words,
)


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


@pytest.mark.parametrize(
    ("title", "language"),
    [
        # names MangaUpdates gives without a language, in the recorded fixtures
        ("Chensoo Man", "ja-ro"),
        ("Tongari Booshi no Atorie", "ja-ro"),
        ("Tongari Bōshi no Atorie", "ja-ro"),
        ("Kaguya-sama wa Kokurasetai", "ja-ro"),
        ("Asrama Topi Lancip", "latin"),
        ("Pondok Penyihir Topi Lancip", "latin"),
        ("Atelier of Witch Hat (Indonesian)", "id"),
        ("Niepamięć Panny Zmierzchu (Polish)", "pl"),
        ("Niepamięć Panny Zmierzchu", "pl"),
        ("Cadı Şapkası Atölyesi", "tr"),
        ("Ateliér špičatých klobouků", "cs"),
        ("Xưởng Phép Thuật", "vi"),
        ("El Atelier del Sombrero Puntiagudo", "es"),
        ("Atelier of Witch Hat: Das Geheimnis der Hexen", "de"),
        ("Kaguya Ingin Dicintai: Perang Cerdik dalam Cinta dan Akal", "id"),
        ("Berserk: The Prototype", "en"),
        ("La Jeune Fille du crépuscule x Amnésie", "fr"),
        ("Koukin Otome x Amnesia", "latin"),
        ("Chainsaw Man: Public Safety Saga", "latin"),
        ("Chain saw man", "latin"),
        ("Berserk", "latin"),
        ("チェンソーマン", "ja"),
        ("Человек-бензопила", "ru"),
    ],
)
def test_language_of(title: str, language: str) -> None:
    assert language_of(title) == language


def test_romaji_needs_japanese_syllables_and_a_sign_of_them() -> None:
    assert is_romaji("Tongari Boushi no Atorie")
    assert not is_romaji("Tongari Boushi no Atelier")  # "atelier": no Japanese syllables
    assert not is_romaji("Nada me puede")  # Japanese syllables, but nothing Japanese
    assert not is_romaji("Horimiya")  # a name alone says nothing
