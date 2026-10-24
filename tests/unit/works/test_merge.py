"""shelfdrop.works.merge."""

import json
from pathlib import Path
from typing import Final

import pytest

from shelfdrop.works.merge import french_edition_names, join_merges, merge
from shelfdrop.works.ranking import rank
from shelfdrop.works.repository import CANDIDATES
from shelfdrop.works.types import Candidate, Name, SourceName, WorkMerge
from tests.unit.works.cases import MERGE_CASES, MergeCase

ANSWERS: Final = Path(__file__).parent / "candidates"


def candidate_of(
    source: SourceName,
    source_id: str,
    title: str,
    *,
    names: tuple[Name, ...] = (),
    authors: tuple[str, ...] = (),
    volumes_fr: int | None = None,
    external_ids: dict[str, str] | None = None,
    year: int | None = None,
) -> Candidate:
    return Candidate(
        source=source,
        source_id=source_id,
        title=title,
        names=names,
        authors=authors,
        volumes_fr=volumes_fr,
        external_ids=external_ids or {},
        year=year,
    )


def test_merge_by_external_id() -> None:
    kitsu = candidate_of("kitsu", "1", "Chainsaw Man", external_ids={"myanimelist": "116778"})
    mal = candidate_of("myanimelist", "116778", "Chainsaw Man")
    assert len(merge([kitsu, mal])) == 1


def test_merge_by_name_needs_compatible_authors() -> None:
    a = candidate_of("mangaupdates", "1", "Amnesia", authors=("Someone Else",))
    b = candidate_of("kitsu", "2", "Amnesia", authors=("Maybe",))
    assert len(merge([a, b])) == 2


def test_a_record_without_an_author_does_not_chain_two_works() -> None:
    """The BnF record shares the name of both: it may be either, so it stays alone."""
    found = merge(
        [
            candidate_of("myanimelist", "1", "Blue Period", authors=("Tsubasa Yamaguchi",)),
            candidate_of(
                "mangaupdates",
                "2",
                "Mizuiro Jidai",
                names=(Name(title="Blue Period", language="latin"),),
                authors=("Yuu Yabuuchi",),
            ),
            candidate_of("bnf", "ark", "Blue period"),
        ]
    )
    assert len(found) == 3


def test_a_group_without_an_author_joins_the_one_work_it_may_be() -> None:
    found = merge(
        [
            candidate_of("mangaupdates", "1", "Blue Period", authors=("Tsubasa Yamaguchi",)),
            candidate_of("kitsu", "2", "Blue Period"),
            candidate_of("bnf", "ark", "Blue period"),
        ]
    )
    assert [len(members) for _, members in found] == [3]


def test_a_group_without_an_author_stays_apart_from_a_work_of_another_time() -> None:
    found = merge(
        [
            candidate_of("mangaupdates", "1", "Blue Period", authors=("A Body",), year=2017),
            candidate_of("kitsu", "2", "Blue Period", year=1991),
        ]
    )
    assert len(found) == 2


def test_a_source_lists_a_work_once() -> None:
    """Two entries of MyAnimeList are two works, even when a record shares both names."""
    found = merge(
        [
            candidate_of(
                "myanimelist", "1", "Blue Period", authors=("Tsubasa Yamaguchi",), year=2017
            ),
            candidate_of(
                "myanimelist",
                "2",
                "Nude Model",
                names=(Name(title="Blue Period", language="latin"),),
                authors=("Tsubasa Yamaguchi",),
                year=2015,
            ),
            candidate_of("bnf", "ark", "Blue period", authors=("Tsubasa Yamaguchi",)),
        ]
    )
    assert [[m.source_id for m in members] for _, members in found] == [["1", "ark"], ["2"]]


def test_the_romanizations_of_an_author_are_the_same_author() -> None:
    found = merge(
        [
            candidate_of("mangaupdates", "1", "Dusk Maiden of Amnesia", authors=("Maybe",)),
            candidate_of("bnf", "ark", "Dusk maiden of amnesia", authors=("Meibii",)),
        ]
    )
    assert len(found) == 1


def answers_of(case: MergeCase) -> list[Candidate]:
    answers = json.loads((ANSWERS / f"{case.slug}.json").read_text())
    return [c for found in answers.values() for c in CANDIDATES.validate_python(found)]


@pytest.mark.parametrize("case", MERGE_CASES, ids=[c.slug for c in MERGE_CASES])
def test_the_works_of_a_name_stay_apart(case: MergeCase) -> None:
    merged = merge(answers_of(case))
    works, _ = rank(case.query, merged, manga=case.kind == "manga")

    first = works[0]
    assert set(first.keys) == set(case.first)
    assert first.year == case.year
    assert first.authors == (case.author,)
    owners = [next(w.id for w, _ in merged if key in w.keys) for key in case.apart]
    assert len(set(owners)) == len(case.apart)
    assert first.id not in owners


def test_bnf_casing_loses_but_stays_french() -> None:
    mu = candidate_of(
        "mangaupdates",
        "1",
        "Tasogare Otome x Amnesia",
        names=(Name(title="Dusk Maiden of Amnesia", language="latin"),),
    )
    bnf = candidate_of(
        "bnf",
        "ark",
        "Dusk maiden of amnesia",
        names=(Name(title="Dusk maiden of amnesia", language="fr"),),
        volumes_fr=10,
    )
    [(work, _)] = merge([mu, bnf])
    assert work.shelf_name == "Dusk Maiden of Amnesia"
    assert work.volumes_fr == 10


def test_abbreviations_and_parts_are_not_checked() -> None:
    work, _ = merge(
        [
            candidate_of(
                "kitsu",
                "1",
                "Chainsaw Man",
                names=(
                    Name(title="Chainsaw Man", language="en"),
                    Name(title="CSM", language="latin"),
                    Name(title="Chainsawman", language="latin"),
                    Name(title="Chainsaw Man: Public Safety Saga", language="latin"),
                    Name(title="チェンソーマン", language="ja"),
                ),
            ),
        ]
    )[0]
    checked = {n.title for n in work.names if n.checked}
    assert checked == {"Chainsaw Man"}


def test_a_name_in_an_unknown_or_other_language_is_not_checked() -> None:
    """MangaUpdates gives its names without a language: a Polish, Indonesian or unknown name is
    shown, but not searched by default."""
    work, _ = merge(
        [
            candidate_of(
                "mangaupdates",
                "1",
                "Tongari Boushi no Atelier",
                names=(
                    Name(title="Asrama Topi Lancip", language="latin"),
                    Name(title="Atelier spiczastych kapeluszy (Polish)", language="latin"),
                    Name(title="Cadı Şapkası Atölyesi", language="latin"),
                    Name(title="Tongari Booshi no Atorie", language="latin"),
                ),
            ),
        ]
    )[0]
    by_title = {n.title: n for n in work.names}
    assert by_title["Asrama Topi Lancip"].language == "latin"
    assert not by_title["Asrama Topi Lancip"].checked
    assert by_title["Atelier spiczastych kapeluszy (Polish)"].language == "pl"
    assert not by_title["Atelier spiczastych kapeluszy (Polish)"].checked
    assert by_title["Cadı Şapkası Atölyesi"].language == "tr"
    assert not by_title["Cadı Şapkası Atölyesi"].checked
    assert by_title["Tongari Booshi no Atorie"].language == "ja-ro"
    assert by_title["Tongari Booshi no Atorie"].checked


def test_the_title_of_the_work_is_checked_whatever_its_language() -> None:
    """MangaUpdates alone, its title in no language the rules know: it is still searched."""
    work, _ = merge([candidate_of("mangaupdates", "1", "Berserk")])[0]
    assert [(n.title, n.language, n.checked) for n in work.names] == [("Berserk", "latin", True)]


def test_the_language_a_source_gives_wins_over_a_guess() -> None:
    mu = candidate_of(
        "mangaupdates", "1", "Chainsaw Man", names=(Name(title="Testere Adam", language="latin"),)
    )
    mangadex = candidate_of(
        "mangadex",
        "2",
        "Chainsaw Man",
        names=(
            Name(title="Testere Adam", language="tr"),
            Name(title="Chainsaw Man", language="en"),
        ),
    )
    [(work, _)] = merge([mu, mangadex])
    adam = next(n for n in work.names if n.title == "Testere Adam")
    assert adam.language == "tr"
    assert not adam.checked


def test_a_guessed_language_comes_after_a_given_one() -> None:
    """Six names at most: the romaji a source gave goes before the romaji guessed."""
    guessed = tuple(
        Name(title=f"Tongari Booshi no Atorie {n}", language="latin") for n in "abcdefg"
    )
    work, _ = merge(
        [
            candidate_of(
                "kitsu",
                "1",
                "Witch Hat Atelier",
                names=(
                    Name(title="Witch Hat Atelier", language="en"),
                    *guessed,
                    Name(title="Tongari Boushi no Atelier", language="ja-ro"),
                ),
            )
        ]
    )[0]
    checked = [n.title for n in work.names if n.checked]
    assert checked[:2] == ["Witch Hat Atelier", "Tongari Boushi no Atelier"]
    assert len(checked) == 6


def test_the_bnf_is_asked_again_under_a_name_of_the_work() -> None:
    """'Battle Angel Alita' finds Gunnm; the BnF knows its French edition as 'Gunnm'."""
    gunnm, _ = merge(
        [
            candidate_of(
                "kitsu",
                "1",
                "Battle Angel Alita",
                names=(
                    Name(title="Battle Angel Alita", language="en"),
                    Name(title="Gunnm", language="ja-ro"),
                ),
            )
        ]
    )[0]
    assert french_edition_names([gunnm], "Battle Angel Alita") == ["Gunnm"]


def test_a_french_name_is_asked_first_and_a_work_the_bnf_found_is_not() -> None:
    [(found, _)] = merge(
        [
            candidate_of(
                "kitsu",
                "1",
                "Witch Hat Atelier",
                names=(Name(title="L'atelier des sorciers", language="fr"),),
                authors=("Kamome Shirahama",),
            ),
            candidate_of(
                "bnf", "ark", "L'atelier des sorciers", authors=("Kamome Shirahama",), volumes_fr=15
            ),
        ]
    )
    [(other, _)] = merge(
        [
            candidate_of(
                "mangadex",
                "2",
                "Tongari Boushi no Atelier",
                names=(
                    Name(title="Witch Hat Atelier", language="en"),
                    Name(title="L'Atelier des sorcières", language="fr"),
                ),
            )
        ]
    )
    assert "bnf" in found.sources
    assert french_edition_names([found, other], "Witch Hat") == ["L'Atelier des sorcières"]
    assert french_edition_names([other], "L'atelier des sorcières") == ["Witch Hat Atelier"]


def test_a_merge_by_hand_joins_its_works_in_the_place_of_the_first() -> None:
    found = merge(
        [
            candidate_of("kitsu", "1", "Tongari Boushi no Atelier", authors=("Kamome Shirahama",)),
            candidate_of("mangaupdates", "9", "Berserk"),
            candidate_of("bnf", "ark", "L'Atelier des sorciers"),
        ]
    )
    joined = join_merges(
        found,
        [
            WorkMerge(
                id=4,
                family="manga",
                keys=("kitsu:1", "bnf:ark"),
                shelf_name="L'Atelier des sorciers",
            )
        ],
    )

    assert [w.shelf_name for w, _ in joined] == ["L'Atelier des sorciers", "Berserk"]
    work, members = joined[0]
    assert (work.id, work.merge_id) == ("kitsu:1", 4)
    assert [p.id for p in work.parts] == ["kitsu:1", "bnf:ark"]
    assert work.parts[0].title == "Tongari Boushi no Atelier"
    assert work.keys == ("kitsu:1", "bnf:ark")
    assert {m.source for m in members} == {"kitsu", "bnf"}
    assert work.authors == ("Kamome Shirahama",)


def test_a_merge_whose_search_found_one_work_changes_nothing() -> None:
    found = merge([candidate_of("kitsu", "1", "Berserk")])
    merges = [WorkMerge(id=1, family="manga", keys=("kitsu:1", "kitsu:2"), shelf_name="Other")]

    assert join_merges(found, merges) == found
