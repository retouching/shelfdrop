"""shelfdrop.downloads.states: what the page shows of a download (plan section 3, points 3
and 10)."""

import dataclasses

import pytest

from shelfdrop.clients.types import TorrentInfo
from shelfdrop.downloads.states import category_of, progress_of
from shelfdrop.downloads.types import Download, Progress, Stage
from shelfdrop.releases.types import Volumes

SENT = Download(
    id=1,
    info_hash="a" * 40,
    release_id="0123456789abcdef",
    title="Berserk.T01.FRENCH.CBZ",
    indexer="Nyaa.si",
    size=1000,
    download_url="http://prowlarr.test/1/download?link=x",
    work_id="mangaupdates:1",
    work_name="Berserk",
    author="Kentaro Miura",
    series="Berserk",
    volumes=Volumes(kind="single", first=1, last=1),
    kind="manga",
    mode="auto",
    category="manga",
    stage="sent",
    failure=None,
    attempts=1,
    created_at=0,
    created_by="sylvain",
    added_at=0,
)


def torrent(state: str, progress: float = 0.5, speed: int = 2048, eta: int = 96) -> TorrentInfo:
    return TorrentInfo(
        hash="a" * 40,
        name="Berserk",
        state=state,
        progress=progress,
        speed=speed,
        eta=eta,
        category="manga",
    )


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        (
            torrent("downloading", 0.776),
            Progress(state="downloading", percent=77, speed=2048, eta=96),
        ),
        (torrent("stalledDL", speed=0), Progress(state="downloading", percent=50, speed=0, eta=96)),
        (
            torrent("forcedDL", eta=8640000),
            Progress(state="downloading", percent=50, speed=2048, eta=0),
        ),
        (torrent("metaDL", 0), Progress(state="waiting")),
        (torrent("queuedDL"), Progress(state="waiting")),
        (torrent("stoppedDL"), Progress(state="waiting")),
        (torrent("checkingResumeData"), Progress(state="waiting")),
        (torrent("uploading", 1), Progress(state="placing")),
        (torrent("stalledUP", 1), Progress(state="placing")),
        (torrent("stoppedUP", 1), Progress(state="placing")),
        (torrent("moving", 1), Progress(state="placing")),
        (None, Progress(state="waiting")),
    ],
)
def test_a_download_sent_shows_what_qbittorrent_says(
    info: TorrentInfo | None, expected: Progress
) -> None:
    assert progress_of(SENT, info) == expected


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        ("sending", Progress(state="waiting")),
        ("completed", Progress(state="placing")),
        ("failed", Progress(state="failed", reason="not_received")),
    ],
)
def test_a_download_not_sent_or_completed_shows_its_stage(stage: Stage, expected: Progress) -> None:
    download = dataclasses.replace(SENT, stage=stage)

    assert progress_of(download, torrent("downloading")) == expected


def test_a_manual_download_completed_is_to_place_and_a_duplicate_says_so() -> None:
    manual = dataclasses.replace(SENT, mode="manual", category="shelfdrop-manual")

    assert progress_of(manual, torrent("uploading", 1)) == Progress(
        state="to_place", unplaced="manual"
    )
    assert progress_of(dataclasses.replace(manual, stage="completed"), None).state == "to_place"
    duplicate = dataclasses.replace(SENT, stage="failed", failure="duplicate")
    assert progress_of(duplicate, None) == Progress(state="failed", reason="duplicate")


def test_a_download_placed_shows_where_and_one_left_to_ranger_why() -> None:
    placed = dataclasses.replace(SENT, stage="placed", destination="BD & Mangas \u203a Berserk")
    left = dataclasses.replace(SENT, stage="unplaced", unplaced="chapters")
    merging = dataclasses.replace(SENT, stage="completed", placing_percent=40)

    assert progress_of(placed, None) == Progress(
        state="placed", destination="BD & Mangas \u203a Berserk"
    )
    assert progress_of(left, None) == Progress(state="to_place", unplaced="chapters")
    assert progress_of(merging, None) == Progress(state="placing", percent=40)


def test_the_category_is_the_kind_or_the_one_of_the_manual_downloads() -> None:
    assert category_of("manga", "auto") == "manga"
    assert category_of("audiobook", "auto") == "audiobook"
    assert category_of("ebook", "manual") == "shelfdrop-manual"
