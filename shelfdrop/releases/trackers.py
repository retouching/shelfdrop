"""The trackers from the indexers of Prowlarr: nothing is written in the code but the order of
the first import, the tracker never allowed for the automatic downloads at first, and the
categories of each kind of a tracker whose categories were never chosen."""

import re
from collections.abc import Sequence
from typing import Final

from shelfdrop.releases.types import (
    DEFAULT_CATEGORIES,
    Indexer,
    Tracker,
    TrackerChoice,
    TrackerGroup,
)
from shelfdrop.works.types import Kind

# The order of the first import (Nyaa, The Old School, ABN, the others, C411 last), and the
# tracker left out of the automatic downloads at first (decided on 2026-10-21).
FIRST_ORDER: Final = (
    re.compile(r"nyaa", re.IGNORECASE),
    re.compile(r"old\s*school|\btos\b", re.IGNORECASE),
    re.compile(r"abnormal|\babn\b", re.IGNORECASE),
)
LAST: Final = re.compile(r"c411", re.IGNORECASE)


def first_rank(name: str) -> int:
    for rank, pattern in enumerate(FIRST_ORDER):
        if pattern.search(name):
            return rank
    return len(FIRST_ORDER) + (1 if LAST.search(name) else 0)


def new_tracker(indexer: Indexer) -> Tracker:
    return Tracker(
        indexer_id=indexer.id,
        name=indexer.name,
        language=indexer.language,
        prowlarr_enabled=indexer.enabled,
        used=True,
        auto=not LAST.search(indexer.name),
        available=indexer.categories,
    )


def merge_trackers(saved: Sequence[Tracker], indexers: Sequence[Indexer]) -> list[Tracker]:
    """The trackers after a read of Prowlarr: the torrent indexers alone (qBittorrent downloads
    torrents), the saved ones in their order and with their choices, their name, language and
    state and categories taken from Prowlarr; an indexer gone from Prowlarr goes; a new one
    comes last, asked, with the default categories. At the first import, the order is
    FIRST_ORDER. A category chosen that Prowlarr no longer gives stays chosen."""
    found = {i.id: i for i in indexers if i.protocol in ("torrent", "")}
    kept = [
        Tracker(
            indexer_id=t.indexer_id,
            name=found[t.indexer_id].name,
            language=found[t.indexer_id].language,
            prowlarr_enabled=found[t.indexer_id].enabled,
            used=t.used,
            auto=t.auto,
            available=found[t.indexer_id].categories,
            chosen=t.chosen,
        )
        for t in saved
        if t.indexer_id in found
    ]
    known = {t.indexer_id for t in saved}
    added = [new_tracker(i) for i in found.values() if i.id not in known]
    if not saved:
        added.sort(key=lambda t: first_rank(t.name))
    return kept + added


def ordered_choices(saved: Sequence[Tracker], choices: Sequence[TrackerChoice]) -> list[Tracker]:
    """The saved trackers in the order of `choices`; one not chosen keeps its choices and comes
    after. A tracker not asked is never automatic; choices without categories keep those
    saved."""
    by_id = {t.indexer_id: t for t in saved}
    result: list[Tracker] = []
    for choice in choices:
        tracker = by_id.pop(choice.indexer_id, None)
        if tracker is not None:
            result.append(
                Tracker(
                    indexer_id=tracker.indexer_id,
                    name=tracker.name,
                    language=tracker.language,
                    prowlarr_enabled=tracker.prowlarr_enabled,
                    used=choice.used,
                    auto=choice.auto and choice.used,
                    available=tracker.available,
                    chosen=(
                        tracker.chosen
                        if choice.categories is None
                        else chosen_of(choice.categories)
                    ),
                )
            )
    return result + list(by_id.values())


def chosen_of(categories: dict[Kind, tuple[int, ...]]) -> dict[Kind, tuple[int, ...]] | None:
    """The categories chosen as they are kept: None when each kind has its default ones, so
    that the tracker shows the default ones again."""
    if all(categories.get(k, d) == d for k, d in DEFAULT_CATEGORIES.items()):
        return None
    return categories


def categories_of(tracker: Tracker, kind: Kind) -> tuple[int, ...]:
    """The categories searched in `tracker` for `kind`: those chosen, else the default."""
    if tracker.chosen is None or kind not in tracker.chosen:
        return DEFAULT_CATEGORIES[kind]
    return tracker.chosen[kind]


def unknown_categories(saved: Sequence[Tracker], choices: Sequence[TrackerChoice]) -> list[int]:
    """The indexer ids of the choices that name a category the tracker does not know: neither
    given by Prowlarr, nor the default of the kind, nor already chosen."""
    by_id = {t.indexer_id: t for t in saved}
    refused: list[int] = []
    for choice in choices:
        tracker = by_id.get(choice.indexer_id)
        if tracker is None or choice.categories is None:
            continue
        known = {c.id for c in tracker.available}
        for kind, ids in choice.categories.items():
            allowed = known | set(DEFAULT_CATEGORIES[kind]) | set(categories_of(tracker, kind))
            if not set(ids) <= allowed:
                refused.append(choice.indexer_id)
                break
    return refused


def search_groups(trackers: Sequence[Tracker], kind: Kind) -> list[TrackerGroup]:
    """The trackers asked for `kind` (asked, on in Prowlarr, with a category for it), grouped by
    their categories: one Prowlarr request per group. The groups in the order of their first
    tracker; the categories and the ids of a group sorted, for a stable key of the cache."""
    groups: dict[tuple[int, ...], list[int]] = {}
    for tracker in trackers:
        categories = tuple(sorted(set(categories_of(tracker, kind))))
        if tracker.used and tracker.prowlarr_enabled and categories:
            groups.setdefault(categories, []).append(tracker.indexer_id)
    return [
        TrackerGroup(categories=categories, indexer_ids=tuple(sorted(ids)))
        for categories, ids in groups.items()
    ]
