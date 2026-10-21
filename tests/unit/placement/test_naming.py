"""shelfdrop.placement.naming: the names of the shelf, as the scripts of the user wrote them."""

import pytest

from shelfdrop.placement.naming import (
    book_folder,
    book_name,
    chapter_name,
    chapter_sort_name,
    comic_name,
    file_volume,
    safe,
    volume_title,
)


def test_a_volume_of_manga_is_its_series_and_its_number() -> None:
    assert comic_name("Chainsaw Man", 1, ".CBZ") == "Chainsaw Man - T01.cbz"
    assert (
        comic_name("Kaguya-sama - Love is War", 28, ".cbz") == "Kaguya-sama - Love is War - T28.cbz"
    )


def test_a_chapter_placed_alone_names_its_volume_when_it_has_one() -> None:
    assert chapter_name("Chainsaw Man", 23, 206, ".cbz") == "Chainsaw Man - T23 - Ch. 206.cbz"
    assert chapter_name("Chainsaw Man", None, 230, ".cbz") == "Chainsaw Man - Ch. 230.cbz"
    assert chapter_name("Chainsaw Man", None, 12.5, ".cbz") == "Chainsaw Man - Ch. 12.5.cbz"
    assert chapter_name("Chainsaw Man", None, 233, ".cbz", 236) == "Chainsaw Man - Ch. 233-236.cbz"


def test_a_chapter_alone_sorts_between_its_volumes_in_its_order() -> None:
    names = [
        "Chainsaw Man - T22",
        chapter_sort_name("Chainsaw Man", 22, 230.5),
        chapter_sort_name("Chainsaw Man", 22, 230),
        "Chainsaw Man - T23",
        chapter_sort_name("Chainsaw Man", None, 1),
        "Chainsaw Man - T01",
    ]

    assert sorted(names) == [
        chapter_sort_name("Chainsaw Man", None, 1),
        "Chainsaw Man - T01",
        "Chainsaw Man - T22",
        chapter_sort_name("Chainsaw Man", 22, 230),
        chapter_sort_name("Chainsaw Man", 22, 230.5),
        "Chainsaw Man - T23",
    ]


def test_a_book_has_its_author_its_series_and_its_volume() -> None:
    assert book_folder("Robin Hobb", "Les Aventuriers de la mer", 1, "Le Vaisseau magique") == (
        "Robin Hobb",
        "Les Aventuriers de la mer",
        "01 - Le Vaisseau magique",
    )
    assert (
        book_name("Les Aventuriers de la mer", 1, "Le Vaisseau magique", ".EPUB", None)
        == "Les Aventuriers de la mer - T01 - Le Vaisseau magique.epub"
    )
    assert (
        book_name("La Mémoire des os", 2, "La phalène et l'araignée", ".mp3", 7)
        == "La Mémoire des os - T02 - La phalène et l'araignée - 007.mp3"
    )


def test_a_name_never_holds_a_separator() -> None:
    assert safe("AC/DC: live?") == "AC DC live"
    assert safe("..") == "_"
    assert safe("Rosario+Vampire") == "Rosario+Vampire"


@pytest.mark.parametrize(
    ("stem", "volume"),
    [
        ("Berserk T41", 41),
        ("Jujutsu.Kaisen.T25.FRENCH.CBZ.eBook-NOTAG", 25),
        ("Kaguya-sama Tome 3", 3),
        ("Gunnm Vol.05", 5),
        ("Horimiya v16", 16),
        ("Demon Slayer 12", 12),
        ("Demon Slayer (01-23) (Gotoge)", None),
        ("Bonne nuit Punpun [Digital-1920] (2021)", None),
    ],
)
def test_the_volume_of_a_file_is_read_as_comics_rename_read_it(
    stem: str, volume: int | None
) -> None:
    assert file_volume(stem) == volume


@pytest.mark.parametrize(
    ("release", "volume", "title"),
    [
        (
            "Robin.Hobb.Les.aventuriers.de.la.mer.01.Le.vaisseau.magique.2001.FRENCH.MP3",
            1,
            "Le vaisseau magique",
        ),
        ("Ne.Cede.Jamais.David.Goggins.FRENCH.MP3", 1, "Ne cède jamais"),
        ("Memoire.Des.Os.T02.La.phalene.et.l.araignee.FRENCH.M4B", 2, "La phalene et l araignee"),
    ],
)
def test_the_title_of_a_volume_comes_after_its_number_and_before_its_tags(
    release: str, volume: int, title: str
) -> None:
    assert volume_title(release, volume, "Ne cède jamais") == title
