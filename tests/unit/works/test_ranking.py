"""shelfdrop.works.ranking."""

from shelfdrop.works.ranking import name_match


def test_name_match() -> None:
    assert name_match("Dusk Maiden of Amnesia", "Dusk Maiden of Amnesia") == 1.0
    assert name_match("Dusk Maiden of Amnesia", "Amnesia") < name_match(
        "Dusk Maiden of Amnesia", "Dusk Maiden of Amnesia Anthology"
    )
    assert name_match("Berserk", "One Piece") == 0.0
