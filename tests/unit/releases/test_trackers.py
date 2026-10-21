"""shelfdrop.releases.trackers: the trackers read from Prowlarr (section 3, point 13)."""

from shelfdrop.releases.trackers import merge_trackers, ordered_choices
from shelfdrop.releases.types import Indexer, Tracker


def indexer(id_: int, name: str, *, enabled: bool = True, protocol: str = "torrent") -> Indexer:
    return Indexer(id=id_, name=name, enabled=enabled, language="fr-FR", protocol=protocol)


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
    trackers = ordered_choices(saved, [(4, True, True), (1, False, True)])
    assert [(t.name, t.used, t.auto) for t in trackers] == [
        ("C411", True, True),
        ("Nyaa.si", False, False),
        ("Abnormal", True, True),
        ("TorrentLeech", True, True),
    ]
