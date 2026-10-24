"""shelfdrop.releases.trackers: the trackers read from Prowlarr (section 3, point 13) and their
categories."""

from shelfdrop.releases.trackers import (
    categories_of,
    merge_trackers,
    ordered_choices,
    search_groups,
    unknown_categories,
)
from shelfdrop.releases.types import Category, Indexer, Tracker, TrackerChoice, TrackerGroup
from shelfdrop.works.types import Kind

LITERATURE = Category(id=100920, name="Literature")
COMICS = Category(id=7030, name="Books/Comics")


def indexer(
    id_: int,
    name: str,
    *,
    enabled: bool = True,
    protocol: str = "torrent",
    categories: tuple[Category, ...] = (),
) -> Indexer:
    return Indexer(
        id=id_,
        name=name,
        enabled=enabled,
        language="fr-FR",
        protocol=protocol,
        categories=categories,
    )


def tracker(
    id_: int,
    *,
    used: bool = True,
    enabled: bool = True,
    chosen: dict[Kind, tuple[int, ...]] | None = None,
    available: tuple[Category, ...] = (COMICS,),
) -> Tracker:
    return Tracker(
        indexer_id=id_,
        name=f"T{id_}",
        language=None,
        prowlarr_enabled=enabled,
        used=used,
        auto=True,
        available=available,
        chosen=chosen,
    )


INDEXERS = [
    indexer(4, "C411"),
    indexer(3, "Abnormal"),
    indexer(7, "TorrentLeech"),
    indexer(1, "Nyaa.si"),
    indexer(5, "YggTorrent", enabled=False),
    indexer(2, "The Old School"),
    indexer(6, "NZBgeek", protocol="usenet"),
]


def test_the_first_import_orders_and_leaves_c411_out_of_the_automatic_downloads() -> None:
    trackers = merge_trackers([], INDEXERS)
    assert [t.name for t in trackers] == [
        "Nyaa.si",
        "The Old School",
        "Abnormal",
        "TorrentLeech",
        "YggTorrent",
        "C411",
    ]
    assert all(t.used for t in trackers)
    assert [t.name for t in trackers if not t.auto] == ["C411"]
    assert [t.name for t in trackers if not t.prowlarr_enabled] == ["YggTorrent"]


def test_a_read_again_keeps_the_choices_drops_the_gone_and_adds_the_new() -> None:
    saved = [
        Tracker(
            indexer_id=4, name="C411", language="fr-FR", prowlarr_enabled=True, used=True, auto=True
        ),
        Tracker(
            indexer_id=9, name="Gone", language=None, prowlarr_enabled=True, used=True, auto=True
        ),
        Tracker(
            indexer_id=1, name="Nyaa", language=None, prowlarr_enabled=True, used=False, auto=False
        ),
    ]
    trackers = merge_trackers(
        saved, [indexer(1, "Nyaa.si", enabled=False), indexer(4, "C411"), indexer(8, "New")]
    )
    assert [(t.indexer_id, t.name, t.used, t.auto, t.prowlarr_enabled) for t in trackers] == [
        (4, "C411", True, True, True),
        (1, "Nyaa.si", False, False, False),
        (8, "New", True, True, True),
    ]


def test_choices_reorder_and_a_tracker_not_asked_is_never_automatic() -> None:
    saved = merge_trackers([], INDEXERS[:4])
    trackers = ordered_choices(
        saved,
        [
            TrackerChoice(indexer_id=4, used=True, auto=True),
            TrackerChoice(indexer_id=1, used=False, auto=True),
        ],
    )
    assert [(t.name, t.used, t.auto) for t in trackers] == [
        ("C411", True, True),
        ("Nyaa.si", False, False),
        ("Abnormal", True, True),
        ("TorrentLeech", True, True),
    ]


def test_a_read_again_takes_the_categories_of_prowlarr_and_keeps_those_chosen() -> None:
    saved = [tracker(1, chosen={"manga": (100920,)}, available=())]

    trackers = merge_trackers(
        saved,
        [
            indexer(1, "Nyaa.si", categories=(COMICS, LITERATURE)),
            indexer(2, "New", categories=(COMICS,)),
        ],
    )

    assert [(t.available, t.chosen) for t in trackers] == [
        ((COMICS, LITERATURE), {"manga": (100920,)}),
        ((COMICS,), None),
    ]


def test_a_tracker_never_chosen_searches_the_default_categories() -> None:
    never = tracker(1)
    some = tracker(2, chosen={"manga": (7030, 100920), "audiobook": ()})

    assert [categories_of(never, k) for k in ("manga", "ebook", "audiobook")] == [
        (7030,),
        (7020,),
        (3030,),
    ]
    # A kind left out takes its default; an empty list is not searched.
    assert [categories_of(some, k) for k in ("manga", "ebook", "audiobook")] == [
        (7030, 100920),
        (7020,),
        (),
    ]


def test_choices_without_categories_keep_those_saved() -> None:
    saved = [tracker(1, chosen={"manga": (100920,)}), tracker(2)]

    trackers = ordered_choices(
        saved,
        [
            TrackerChoice(indexer_id=1, used=True, auto=True),
            TrackerChoice(indexer_id=2, used=True, auto=True, categories={"ebook": ()}),
        ],
    )

    assert [t.chosen for t in trackers] == [{"manga": (100920,)}, {"ebook": ()}]


def test_choices_of_the_default_categories_are_the_default_again() -> None:
    saved = [tracker(1, chosen={"manga": (100920,)})]
    defaults: dict[Kind, tuple[int, ...]] = {
        "manga": (7030,),
        "ebook": (7020,),
        "audiobook": (3030,),
    }

    trackers = ordered_choices(
        saved, [TrackerChoice(indexer_id=1, used=True, auto=True, categories=defaults)]
    )

    assert trackers[0].chosen is None


def test_a_category_the_tracker_does_not_know_is_refused() -> None:
    saved = [
        tracker(1, available=(COMICS, LITERATURE)),
        tracker(2, available=(), chosen={"manga": (5070,)}),
    ]

    def choice(id_: int, manga: tuple[int, ...]) -> TrackerChoice:
        return TrackerChoice(indexer_id=id_, used=True, auto=True, categories={"manga": manga})

    # Given by Prowlarr, the default of the kind, or already chosen: known.
    assert unknown_categories(saved, [choice(1, (100920, 7030)), choice(2, (5070, 7030))]) == []
    assert unknown_categories(saved, [choice(1, (156719,)), choice(2, (100920,))]) == [1, 2]
    # A tracker no longer saved is left out, as its choices are.
    assert unknown_categories(saved, [choice(9, (1,))]) == []


def test_the_trackers_asked_are_grouped_by_their_categories_of_the_kind() -> None:
    trackers = [
        tracker(4),
        tracker(1, chosen={"manga": (156719, 100920)}),
        tracker(3),
        tracker(2, chosen={"manga": ()}),
        tracker(5, used=False),
        tracker(6, enabled=False),
        tracker(7, chosen={"manga": (100920, 156719)}),
    ]

    assert search_groups(trackers, "manga") == [
        TrackerGroup(categories=(7030,), indexer_ids=(3, 4)),
        TrackerGroup(categories=(100920, 156719), indexer_ids=(1, 7)),
    ]
    assert search_groups(trackers, "ebook") == [
        TrackerGroup(categories=(7020,), indexer_ids=(1, 2, 3, 4, 7)),
    ]
