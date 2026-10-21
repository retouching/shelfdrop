"""shelfdrop.releases.guess: the volumes of a release title, the query, the relevance (plan 2.4)."""

import pytest

from shelfdrop.releases.guess import clean_query, is_relevant, volumes_of
from shelfdrop.releases.types import Volumes


def single(n: int) -> Volumes:
    return Volumes(kind="single", first=n, last=n)


def pack(first: int, last: int) -> Volumes:
    return Volumes(kind="range", first=first, last=last)


@pytest.mark.parametrize(
    ("title", "volumes"),
    [
        # titles seen on the trackers of the user
        ("Jujutsu.Kaisen.T00.FRENCH.MANGA.CBZ.eBook-PapriKa+", single(0)),
        ("Jujutsu.Kaisen.T18.FRENCH.MANGA.CBZ.eBook-PapriKa+", single(18)),
        ("Jujutsu.kaisen.T23.Gege.AKUTAMI.FRENCH.[CBZ]-ebdz", single(23)),
        ("Jujutsu.kaisen.T25.FRENCH.CBZ.eBook-NEO", single(25)),
        ("Demon.Slave.T09.FRENCH.MANGA.CBZ.eBook-PapriKa+", single(9)),
        ("Demon Slayer (01-23) (Gotoge) (2019) [Digital-1920] (PapriKa+)", pack(1, 23)),
        (
            "DARLING in the FRANXX (01-08) (Code:000-Yabuki) (2022) [Digital-1920] (PapriKa+)",
            pack(1, 8),
        ),
        (
            "DARLING in the FRANXX T02 (Code - 000-Yabuki) (2022) [Digital-1920u] (PapriKa+).cbz",
            single(2),
        ),
        ("Burn the Witch (Kubo) (2021) [Digital-1598] (PapriKa+)", Volumes(kind="unknown")),
        ("Burn.the.Witch.Kubo.2021.FR.[CBZ]-PapriKa", Volumes(kind="unknown")),
        # the formats of the groups named in the plan (NOTAG, NRC.ALLIANCE), written by hand
        ("One.Piece.T01-T11.FRENCH.CBZ.eBook-NOTAG", pack(1, 11)),
        ("One Piece T01 à T11 FRENCH CBZ-NOTAG", pack(1, 11)),
        ("Berserk.[INTEGRALE].FRENCH.CBZ-NRC.ALLIANCE", Volumes(kind="complete")),
        ("Monster Complete Edition FRENCH CBZ", Volumes(kind="complete")),
        ("Kaguya-sama Tome 3 FRENCH", single(3)),
        ("Kaguya-sama Tomes 1 à 3 FRENCH", pack(1, 3)),
        ("Sorcery Fight v04 (2019) (Digital) (1r0n)", single(4)),
        ("Chainsaw Man Vol.01-05 (Digital)", pack(1, 5)),
        ("Chainsaw Man Vol.12 (Digital)", single(12)),
    ],
)
def test_volumes_of(title: str, volumes: Volumes) -> None:
    assert volumes_of(title) == volumes


def test_a_chapter_is_not_a_volume() -> None:
    assert volumes_of("Chainsaw Man Ch. 232 [Digital]").kind == "unknown"


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("Tasogare Otome × Amnesia", "Tasogare Otome x Amnesia"),
        ("Kaguya-sama: Love is War", "Kaguya-sama Love is War"),
        ('Re:Zero "Starting Life"', "Re Zero Starting Life"),
        ("Hey!  Kids?", "Hey Kids"),
        ("L'atelier des sorciers", "L'atelier des sorciers"),
    ],
)
def test_clean_query(text: str, query: str) -> None:
    assert clean_query(text) == query


def test_dusk_maiden_is_not_amnesia() -> None:
    """The 21/10 mistake: a release found under a name must hold every significant word."""
    assert not is_relevant("Amnesia.T01.FRENCH.CBZ.eBook-NOTAG", "Tasogare Otome x Amnesia")
    assert is_relevant(
        "Tasogare.Otome.x.Amnesia.T01.FRENCH.CBZ.eBook-PapriKa+", "Tasogare Otome × Amnesia"
    )
    # Stop words and words of 2 letters are not needed.
    assert is_relevant("Atelier.des.sorciers.T01.FRENCH", "L'Atelier des Sorciers")
