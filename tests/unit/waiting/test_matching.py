"""shelfdrop.waiting.matching: which releases answer a waiting search, and where a search of
chapters stands."""

import dataclasses

import pytest

from shelfdrop.releases.types import Volumes
from shelfdrop.waiting.matching import answers, found, is_done, label, next_chapter
from shelfdrop.waiting.types import Wanted
from tests.unit.downloads.support import release

T23 = Wanted(target="volume", volume=23)
FROM_233 = Wanted(target="chapters", chapter_from=233)


@pytest.mark.parametrize(
    ("title", "volumes", "wanted", "expected"),
    [
        ("Chainsaw.Man.T23.FRENCH.CBZ", Volumes(kind="single", first=23, last=23), T23, True),
        ("Chainsaw.Man.T22.FRENCH.CBZ", Volumes(kind="single", first=22, last=22), T23, False),
        ("Chainsaw.Man.T20-T25.FRENCH", Volumes(kind="range", first=20, last=25), T23, True),
        ("Chainsaw.Man.Integrale", Volumes(kind="complete"), T23, True),
        ("Chainsaw Man", Volumes(kind="unknown"), T23, False),
        ("Chainsaw Man - Ch. 233", Volumes(kind="unknown"), FROM_233, True),
        ("Chainsaw Man Ch.230-236", Volumes(kind="unknown"), FROM_233, True),
        ("Chainsaw Man c232.5", Volumes(kind="unknown"), FROM_233, False),
        ("Chainsaw.Man.T23.FRENCH.CBZ", Volumes(kind="single", first=23, last=23), FROM_233, False),
    ],
)
def test_a_release_answers_only_what_is_waited_for(
    title: str, volumes: Volumes, wanted: Wanted, expected: bool
) -> None:
    assert answers(wanted, dataclasses.replace(release(title), volumes=volumes)) is expected


def test_chapters_with_an_end_and_releases_set_aside() -> None:
    upto = Wanted(target="chapters", chapter_from=233, chapter_to=235)
    kept = release("Chainsaw Man - Ch. 236")
    set_aside = dataclasses.replace(release("Chainsaw Man - Ch. 233"), rejected="score")

    assert not answers(upto, kept)
    assert not answers(Wanted(target="any"), set_aside)
    assert found(FROM_233, [kept, set_aside, release("Chainsaw Man - Ch. 240")]) == 2


def test_a_search_of_chapters_moves_to_the_first_not_placed() -> None:
    assert next_chapter(233, {233.0, 233.5, 234.0, 236.0}) == 235
    assert next_chapter(233, set()) == 233
    assert is_done(Wanted(target="chapters", chapter_from=233, chapter_to=234), [], {233, 234})
    assert not is_done(FROM_233, [], {233, 234})
    assert is_done(T23, [22, 23], set())
    assert not is_done(Wanted(target="any"), [1], set())


def test_the_labels_are_those_of_the_page() -> None:
    assert label(Wanted(target="volume", volume=3)) == "T03"
    assert label(FROM_233) == "Ch. 233 et suivants"
    assert label(Wanted(target="chapters", chapter_from=12.5, chapter_to=20)) == (
        "Ch. 12.5 \u00e0 20"
    )
    assert label(Wanted(target="any")) == "Toute release"
