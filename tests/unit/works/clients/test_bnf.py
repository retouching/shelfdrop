"""shelfdrop.works.clients.bnf: the reading of a record."""

import pytest

from shelfdrop.works.clients.bnf import author_of, split_title


@pytest.mark.parametrize(
    ("raw", "title", "volume"),
    [
        ("Dusk maiden of amnesia. 10 / Maybe", "Dusk maiden of amnesia", 10),
        ("Chainsaw Man T22 - Édition Limitée", "Chainsaw Man", 22),
        ("Chainsaw Man. 13, Spoiler", "Chainsaw Man", 13),
        ("Chainsaw man. Tomes 1 à 3", "Chainsaw man", None),
        (
            "L'atelier des sorciers ([Éd. collector]) Kamome Shirahama",
            "L'atelier des sorciers",
            None,
        ),
        ("Ne cède jamais : libère ton mental", "Ne cède jamais", None),
        ("2.5 Dimensional seduction. 3 / Yu Hashimoto", "2.5 Dimensional seduction", 3),
        ('"Horimiya" : memorial book page 100', "Horimiya", None),
        ("Horimiya. 10.5 / Hero", "Horimiya", None),
        ("Kaguya-sama : love is war. 17", "Kaguya-sama : love is war", 17),
    ],
)
def test_bnf_title(raw: str, title: str, volume: int | None) -> None:
    assert split_title(raw) == (title, volume)


def test_bnf_translators_are_not_authors() -> None:
    assert author_of("Fujimoto, Tatsuki. Auteur du texte") == "Tatsuki Fujimoto"
    assert author_of("Ludmann, Sébastien. Traducteur") is None
