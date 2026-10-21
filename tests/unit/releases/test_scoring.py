"""shelfdrop.releases.scoring: the filter rules and the score of a release (section 3, point 12)."""

from shelfdrop.releases.scoring import compile_rule, invalid_rules, score_of
from shelfdrop.releases.types import FilterRule

FRENCH = FilterRule(name="Français", pattern=r"\b(FRENCH|TRUEFRENCH|VF)\b", regex=True, score=100)
ENGLISH = FilterRule(name="Anglais", pattern="ENG, ENGLISH", regex=False, score=-50)
COLOUR = FilterRule(
    name="Couleur", pattern="FullColor, Couleur", regex=False, score=-15, kinds=("manga",)
)
OFF = FilterRule(name="Coupée", pattern="CBZ", regex=False, score=1000, enabled=False)
RULES = (FRENCH, ENGLISH, COLOUR, OFF)


def test_the_score_is_the_sum_of_the_rules_that_match() -> None:
    total, matches = score_of("Jujutsu.Kaisen.T01.FRENCH.MANGA.CBZ.eBook-PapriKa+", "manga", RULES)
    assert total == 100
    assert [m.name for m in matches] == ["Français"]

    total, _ = score_of("Chainsaw Man FullColor ENGLISH", "manga", RULES)
    assert total == -65


def test_words_are_whole_words_in_any_case() -> None:
    assert score_of("Jujutsu Kaisen english", "manga", RULES)[0] == -50
    assert score_of("Bengali edition", "manga", RULES)[0] == 0  # "ENG" inside a word
    assert score_of("Release_ENG_v2", "manga", RULES)[0] == -50  # "_" separates


def test_a_rule_of_a_kind_and_a_rule_turned_off() -> None:
    assert score_of("Monster FullColor", "ebook", RULES)[0] == 0
    assert score_of("Monster CBZ", "manga", RULES)[0] == 0


def test_an_invalid_or_empty_rule_is_found() -> None:
    broken = FilterRule(name="Cassée", pattern="(FRENCH", regex=True, score=1)
    empty = FilterRule(name="Vide", pattern=" , ", regex=False, score=1)
    assert compile_rule("(FRENCH", True) is None
    assert invalid_rules((FRENCH, broken, ENGLISH, empty)) == [1, 3]
    # An invalid rule gives no points; it never breaks the search.
    assert score_of("FRENCH", "manga", (broken,))[0] == 0
