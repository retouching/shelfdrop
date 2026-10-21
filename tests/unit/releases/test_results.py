"""shelfdrop.releases.results: the releases of a search, set aside, once each, in order
(plan 2.4.3 to 2.4.6, section 3 point 12)."""

from shelfdrop.releases.results import assemble, release_id
from shelfdrop.releases.types import FilterRule, Filters, FoundRelease

NO_FILTERS = Filters(rules=(), minimum=-100)
RANKS = {1: 0, 2: 1, 3: 2, 4: 3}  # Nyaa, The Old School, ABN, C411


def found(
    guid: str, title: str, indexer_id: int = 2, seeders: int = 5, info_hash: str | None = None
) -> FoundRelease:
    return FoundRelease(
        guid=guid,
        title=title,
        indexer_id=indexer_id,
        indexer=str(indexer_id),
        size=1,
        seeders=seeders,
        info_hash=info_hash,
    )


def test_a_release_found_twice_is_kept_once_with_its_first_name() -> None:
    first = found("g1", "Jujutsu Kaisen T01 FRENCH", info_hash="AB")
    again = found("g2", "Jujutsu Kaisen T01 FRENCH (copie)", indexer_id=3, info_hash="ab")
    releases = assemble(
        [("Jujutsu Kaisen", [first]), ("Sorcery Fight", [first, again])],
        kind="manga",
        relevance=False,
        ranks=RANKS,
        filters=NO_FILTERS,
    )
    assert [(r.guid, r.matched_name) for r in releases] == [("g1", "Jujutsu Kaisen")]


def test_no_seed_goes() -> None:
    releases = assemble(
        [("Jujutsu Kaisen", [found("g", "Jujutsu Kaisen T25", seeders=0)])],
        kind="manga",
        relevance=False,
        ranks=RANKS,
        filters=NO_FILTERS,
    )
    assert releases == []


def test_relevance_sets_aside_in_a_work_search_alone() -> None:
    answers = [("Tasogare Otome x Amnesia", [found("g", "Amnesia.T01.FRENCH.CBZ-NOTAG")])]
    work = assemble(answers, kind="manga", relevance=True, ranks=RANKS, filters=NO_FILTERS)
    manual = assemble(answers, kind="manga", relevance=False, ranks=RANKS, filters=NO_FILTERS)
    assert work[0].rejected == "relevance"
    assert manual[0].rejected is None


def test_order_packs_first_then_volumes_then_score_trackers_seeds() -> None:
    filters = Filters(
        rules=(FilterRule(name="Anglais", pattern="ENGLISH", regex=False, score=-50),),
        minimum=-30,
    )
    answers = [
        (
            "Jujutsu Kaisen",
            [
                found("t02", "Jujutsu Kaisen T02 FRENCH", indexer_id=2),
                found("t01-c411", "Jujutsu Kaisen T01 FRENCH", indexer_id=4, seeders=80),
                found("t01-abn", "Jujutsu Kaisen T01 FRENCH", indexer_id=3, seeders=4),
                found("t01-abn-more", "Jujutsu Kaisen T01 FRENCH", indexer_id=3, seeders=40),
                found("t01-en", "Jujutsu Kaisen T01 ENGLISH", indexer_id=1, seeders=99),
                found("pack", "Jujutsu Kaisen (01-26) (PapriKa+)", indexer_id=1),
                found("integrale", "Jujutsu Kaisen [INTEGRALE]", indexer_id=4),
            ],
        )
    ]
    releases = assemble(answers, kind="manga", relevance=True, ranks=RANKS, filters=filters)
    assert [r.guid for r in releases] == [
        "integrale",
        "pack",
        "t01-abn-more",
        "t01-abn",
        "t01-c411",
        "t01-en",
        "t02",
    ]
    english = next(r for r in releases if r.guid == "t01-en")
    assert english.score == -50
    assert english.rejected == "score"
    assert [(m.name, m.score) for m in english.score_rules] == [("Anglais", -50)]


def test_an_indexer_no_longer_listed_comes_last() -> None:
    releases = assemble(
        [
            (
                "X men",
                [found("a", "X men T01", indexer_id=99), found("b", "X men T01", indexer_id=4)],
            )
        ],
        kind="manga",
        relevance=False,
        ranks=RANKS,
        filters=NO_FILTERS,
    )
    assert [r.guid for r in releases] == ["b", "a"]


def test_the_id_is_short_and_stable() -> None:
    assert release_id("https://tos.test/t/101") == release_id("https://tos.test/t/101")
    assert len(release_id("https://tos.test/t/101")) == 16


def test_a_release_kept_from_a_tracker_allowed_may_be_taken_automatically() -> None:
    releases = assemble(
        [
            (
                "Jujutsu Kaisen",
                [
                    found("g1", "Jujutsu Kaisen T01", indexer_id=1),
                    found("g2", "Jujutsu Kaisen T02", indexer_id=4),
                    found("g3", "Jujutsu Kaisen T03 ENGLISH", indexer_id=1),
                ],
            )
        ],
        kind="manga",
        relevance=True,
        ranks=RANKS,
        filters=Filters(
            rules=(FilterRule(name="Anglais", pattern="ENGLISH", regex=False, score=-50),),
            minimum=0,
        ),
        automatic={1, 2, 3},
    )

    assert {r.guid: r.automatic for r in releases} == {"g1": True, "g2": False, "g3": False}
