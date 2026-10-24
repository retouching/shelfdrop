"""shelfdrop.placement.existing: the shelf compared before any placement."""

from shelfdrop.placement.existing import (
    complete_volumes,
    content_of,
    is_chapters_release,
    split_volumes,
)


def test_the_volumes_and_the_chapters_of_a_series_are_read_from_its_files() -> None:
    shelf = content_of(
        [
            "Chainsaw Man - T01.cbz",
            "Chainsaw Man - T02.cbz",
            "Chainsaw Man - T23 - Ch. 206.cbz",
            "Chainsaw Man - Ch. 230.5.cbz",
            "Chainsaw Man - Ch. 233-236.cbz",
            "cover.jpg",
        ]
    )

    assert shelf.volumes == {1, 2}
    assert shelf.chapters == {206.0, 230.5, 233.0, 234.0, 235.0, 236.0}


def test_a_volume_already_there_is_never_added_again() -> None:
    shelf = content_of(["Berserk - T40.cbz", "Berserk - T41.cbz"])

    split = split_volumes(
        [("a/Berserk T40.cbz", 40), ("a/Berserk T42.cbz", 42), ("b/Berserk T42.cbr", 42)], shelf
    )

    assert split.added == (("a/Berserk T42.cbz", 42),)
    assert split.present == (40,)


def test_a_release_in_chapters_is_known_by_its_names_or_its_count() -> None:
    chapters = [f"Chainsaw Man - Ch. {n}.cbz" for n in (1, 2, 3, 4.5, 7)]
    volumes = [f"Chainsaw Man T{n:02d}.cbz" for n in range(1, 12)]
    numbered = [f"Chainsaw Man {n:03d}.cbz" for n in range(1, 501)]

    assert is_chapters_release(chapters, None)
    assert not is_chapters_release(volumes, 11)
    # 500 files for 40 volumes.
    assert is_chapters_release(numbered, 40)
    assert not is_chapters_release(["cover.jpg"], None)


def test_a_volume_is_complete_when_every_chapter_of_its_range_is_there() -> None:
    have = [206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 216.5]

    # T23 = ch. 206 to 214, T24 = ch. 215 to 223.
    assert complete_volumes(have, {23: (206, 214), 24: (215, 223)}) == [23]
