"""shelfdrop.clients.torrents.webui: the torrents of the WebUI API v2 of qBittorrent, their states
read as the generic status of every client (the states of the WebUI API of qBittorrent 5.0;
`pausedUP` and `pausedDL` before 5.0)."""

import pytest

from shelfdrop.clients.torrents.types import TorrentStatus
from shelfdrop.clients.torrents.webui import eta_of, status_of, tags_of, torrent_of


@pytest.mark.parametrize(
    ("state", "progress", "status"),
    [
        ("downloading", 0.5, "downloading"),
        ("forcedDL", 0.5, "downloading"),
        ("stalledDL", 0.5, "stalled"),
        ("metaDL", 0, "waiting"),
        ("forcedMetaDL", 0, "waiting"),
        ("queuedDL", 0.5, "waiting"),
        ("pausedDL", 0.5, "waiting"),
        ("stoppedDL", 0.5, "waiting"),
        ("checkingDL", 0.5, "waiting"),
        ("checkingResumeData", 0.5, "waiting"),
        ("allocating", 0, "waiting"),
        ("moving", 0.5, "waiting"),
        ("unknown", 0.5, "waiting"),
        ("error", 0.5, "error"),
        ("missingFiles", 0.5, "error"),
        ("uploading", 1, "complete"),
        ("stalledUP", 1, "complete"),
        ("stoppedUP", 1, "complete"),
        ("pausedUP", 1, "complete"),
        ("queuedUP", 1, "complete"),
        ("checkingUP", 1, "complete"),
        ("forcedUP", 1, "complete"),
        # All of it, whatever its state: complete.
        ("moving", 1, "complete"),
        ("error", 1, "complete"),
        # A state of seeding before its progress reached 1: complete too, as before.
        ("stalledUP", 0.999, "complete"),
    ],
)
def test_each_state_of_qbittorrent_is_a_generic_status(
    state: str, progress: float, status: TorrentStatus
) -> None:
    assert status_of(state, progress) == status


@pytest.mark.parametrize(
    ("value", "eta"),
    [(96, 96), (0, 0), (8640000, None), (8640001, None), (-1, None), (None, None), ("9", None)],
)
def test_the_time_left_qbittorrent_cannot_tell_is_none(value: object, eta: int | None) -> None:
    assert eta_of(value) == eta


def test_the_tags_are_split_on_their_commas() -> None:
    assert tags_of("a, placé,b") == frozenset({"a", "placé", "b"})
    assert tags_of("") == frozenset()
    assert tags_of(None) == frozenset()


def test_a_torrent_without_its_hash_is_left_out_and_its_figures_are_bounded() -> None:
    info = torrent_of(
        {
            "hash": "AB" * 20,
            "state": "downloading",
            "progress": 1.5,
            "dlspeed": -3,
            "eta": 8640000,
            "tags": "placé",
        }
    )

    assert torrent_of({"name": "x"}) is None
    assert torrent_of("x") is None
    assert info is not None
    assert info.hash == "ab" * 20
    assert (info.status, info.progress, info.speed, info.eta) == ("complete", 1.0, 0, None)
    assert info.placed
    assert info.category == ""
    assert info.content_path == ""
