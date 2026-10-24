"""The trackers from the indexers of Prowlarr: nothing is written in the code but the order of
the first import and the tracker never allowed for the automatic downloads at first."""

import re
from collections.abc import Sequence
from typing import Final

from shelfdrop.releases.types import Indexer, Tracker

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
    )


def merge_trackers(saved: Sequence[Tracker], indexers: Sequence[Indexer]) -> list[Tracker]:
    """The trackers after a read of Prowlarr: the torrent indexers alone (qBittorrent downloads
    torrents), the saved ones in their order and with their choices, their name, language and
    state taken from Prowlarr; an indexer gone from Prowlarr goes; a new one comes last, asked.
    At the first import, the order is FIRST_ORDER."""
    found = {i.id: i for i in indexers if i.protocol in ("torrent", "")}
    kept = [
        Tracker(
            indexer_id=t.indexer_id,
            name=found[t.indexer_id].name,
            language=found[t.indexer_id].language,
            prowlarr_enabled=found[t.indexer_id].enabled,
            used=t.used,
            auto=t.auto,
        )
        for t in saved
        if t.indexer_id in found
    ]
    known = {t.indexer_id for t in saved}
    added = [new_tracker(i) for i in found.values() if i.id not in known]
    if not saved:
        added.sort(key=lambda t: first_rank(t.name))
    return kept + added


def ordered_choices(
    saved: Sequence[Tracker], choices: Sequence[tuple[int, bool, bool]]
) -> list[Tracker]:
    """The saved trackers in the order of `choices` (indexer id, used, auto); one not chosen
    keeps its choices and comes after. A tracker not asked is never automatic."""
    by_id = {t.indexer_id: t for t in saved}
    result: list[Tracker] = []
    for indexer_id, used, auto in choices:
        tracker = by_id.pop(indexer_id, None)
        if tracker is not None:
            result.append(
                Tracker(
                    indexer_id=tracker.indexer_id,
                    name=tracker.name,
                    language=tracker.language,
                    prowlarr_enabled=tracker.prowlarr_enabled,
                    used=used,
                    auto=auto and used,
                )
            )
    return result + list(by_id.values())
