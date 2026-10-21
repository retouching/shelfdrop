"""The releases of a search, from the answers of Prowlarr to each name: kept or set aside, once
each, scored, in the order of the page."""

import hashlib
from collections.abc import Collection, Mapping, Sequence

from shelfdrop.releases.guess import is_relevant, volumes_of
from shelfdrop.releases.scoring import score_of
from shelfdrop.releases.types import Filters, FoundRelease, Rejection, Release, Volumes
from shelfdrop.works.types import Kind

# The rank of a release from an indexer the trackers no longer list: after every other one.
UNRANKED = 10_000


def release_id(guid: str) -> str:
    """A short id of a release, stable across searches: the guid of Prowlarr is a long URL."""
    return hashlib.sha256(guid.encode()).hexdigest()[:16]


def assemble(
    answers: Sequence[tuple[str, Sequence[FoundRelease]]],
    *,
    kind: Kind,
    relevance: bool,
    ranks: Mapping[int, int],
    filters: Filters,
    automatic: Collection[int] = (),
) -> list[Release]:
    """`answers`: the names in the order they were searched, with what Prowlarr found for each.

    A release without seeds goes; a release found twice (same guid or same infohash) is kept
    once, with the first name that found it. With `relevance` (the search of a work), a title
    that misses a significant word of its name is set aside, as is a score under the minimum.
    A release kept from an indexer of `automatic` may be taken by an automatic download.
    """
    seen: set[str] = set()
    found: list[Release] = []
    for name, releases in answers:
        for item in releases:
            keys = {f"guid:{item.guid}"}
            if item.info_hash:
                keys.add(f"hash:{item.info_hash.lower()}")
            if item.seeders <= 0 or keys & seen:
                continue
            seen |= keys
            score, rules = score_of(item.title, kind, filters.rules)
            rejected: Rejection | None = None
            if relevance and not is_relevant(item.title, name):
                rejected = "relevance"
            elif score < filters.minimum:
                rejected = "score"
            found.append(
                Release(
                    id=release_id(item.guid),
                    guid=item.guid,
                    title=item.title,
                    matched_name=name,
                    indexer_id=item.indexer_id,
                    indexer=item.indexer,
                    indexer_rank=ranks.get(item.indexer_id, UNRANKED),
                    info_url=item.info_url,
                    info_hash=item.info_hash,
                    seeders=item.seeders,
                    size=item.size,
                    volumes=volumes_of(item.title),
                    score=score,
                    score_rules=rules,
                    rejected=rejected,
                    automatic=rejected is None and item.indexer_id in automatic,
                    download_url=item.download_url,
                )
            )
    return sorted(found, key=display_order)


def first_volume(volumes: Volumes) -> int:
    return volumes.first if volumes.first is not None else 0


def display_order(release: Release) -> tuple[int, int, int, int, int]:
    """Packs and complete editions first, then volume by volume; for the same volume, the
    score, the order of the trackers, then the seeds."""
    pack = 0 if release.volumes.kind != "single" else 1
    return (
        pack,
        first_volume(release.volumes),
        -release.score,
        release.indexer_rank,
        -release.seeders,
    )
