"""shelfdrop.works.merge."""

from shelfdrop.works.merge import merge
from shelfdrop.works.types import Candidate, Name, SourceName


def candidate_of(
    source: SourceName,
    source_id: str,
    title: str,
    *,
    names: tuple[Name, ...] = (),
    authors: tuple[str, ...] = (),
    volumes_fr: int | None = None,
    external_ids: dict[str, str] | None = None,
) -> Candidate:
    return Candidate(
        source=source,
        source_id=source_id,
        title=title,
        names=names,
        authors=authors,
        volumes_fr=volumes_fr,
        external_ids=external_ids or {},
    )


def test_merge_by_external_id() -> None:
    kitsu = candidate_of("kitsu", "1", "Chainsaw Man", external_ids={"myanimelist": "116778"})
    mal = candidate_of("myanimelist", "116778", "Chainsaw Man")
    assert len(merge([kitsu, mal])) == 1


def test_merge_by_name_needs_compatible_authors() -> None:
    a = candidate_of("mangaupdates", "1", "Amnesia", authors=("Someone Else",))
    b = candidate_of("kitsu", "2", "Amnesia", authors=("Maybe",))
    assert len(merge([a, b])) == 2


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
