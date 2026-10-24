"""The placement of an audiobook in MP3 tracks through the real image: the tracks made by the ffmpeg
of the image, merged by the worker into one M4B with one chapter a track, its length, its cover
attached; the tracks of the shelf removed, those of the torrent kept. And a book:
`<Author>/<Series>/<NN - Title>/...`."""

import json

import httpx
import pytest

from tests.integration.support import (
    SEPARATOR,
    FakeSources,
    Stack,
    send_completed,
    wait_for_download,
)

pytestmark = [pytest.mark.placement, pytest.mark.placement_audio]

TONE = "sine=frequency={}:duration=2"


@pytest.mark.usefixtures("media", "torrent_saved")
def test_mp3_tracks_become_one_m4b_with_its_chapters_its_length_and_its_cover(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Audio Test"
    torrent = "/data/torrents/audiobook/Shelfdrop.Audio.Test.FRENCH.MP3"
    stack.exec_placement("mkdir", "-p", torrent)
    for n in (1, 2, 3):
        stack.exec_placement(
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            TONE.format(220 * n),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            f"{torrent}/Shelfdrop Audio Test - {n:03d}.mp3",
        )
    stack.exec_placement(
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=64x64",
        "-frames:v",
        "1",
        f"{torrent}/cover.jpg",
    )

    download, _ = send_completed(
        client,
        fake_sources,
        name=series,
        kind="audiobook",
        content_path=torrent,
        volumes={"kind": "single", "first": 1, "last": 1},
        author="Shelfdrop Author",
    )

    placed = wait_for_download(
        client, download["id"], lambda d: d["progress"]["state"] in ("placed", "to_place")
    )
    assert placed["progress"]["state"] == "placed", placed
    assert placed["progress"]["destination"] == f"Livres audio{SEPARATOR}{series}"
    folder = f"/data/files/audiobooks/Shelfdrop Author/{series}/01 - {series}"
    listing = stack.exec_placement("ls", "-1", folder)
    m4b = f"{series} - T01 - {series}.m4b"
    assert listing.stdout.splitlines() == [m4b, "cover.jpg"]
    probe = stack.exec_placement(
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_chapters",
        "-show_streams",
        f"{folder}/{m4b}",
    )
    found = json.loads(probe.stdout)
    assert [c["tags"]["title"] for c in found["chapters"]] == [
        "Chapitre 1",
        "Chapitre 2",
        "Chapitre 3",
    ]
    assert [round(float(c["start_time"])) for c in found["chapters"]] == [0, 2, 4]
    assert 5.5 < float(found["format"]["duration"]) < 6.5
    audio = [s for s in found["streams"] if s["codec_type"] == "audio"]
    pictures = [s for s in found["streams"] if s["codec_type"] == "video"]
    assert audio[0]["codec_name"] == "aac"
    assert pictures[0]["disposition"]["attached_pic"] == 1
    # The torrent keeps its tracks: it seeds on.
    assert len(stack.exec_placement("ls", torrent).stdout.split(".mp3")) == 4


@pytest.mark.usefixtures("media", "torrent_saved")
def test_a_book_goes_under_its_author_its_series_and_its_volume(
    client: httpx.Client, fake_sources: FakeSources, stack: Stack
) -> None:
    series = "Shelfdrop Book Test"
    torrent = "/data/torrents/ebook/Shelfdrop.Book.Test.02.Le.Second.Livre.FRENCH.EPUB"
    stack.exec_placement("sh", "-c", f"mkdir -p {torrent} && printf epub > {torrent}/book.epub")

    download, _ = send_completed(
        client,
        fake_sources,
        name=series,
        kind="ebook",
        content_path=torrent,
        volumes={"kind": "single", "first": 2, "last": 2},
        author="Shelfdrop Author",
        title="Shelfdrop.Book.Test.02.Le.Second.Livre.FRENCH.EPUB",
    )

    placed = wait_for_download(
        client, download["id"], lambda d: d["progress"]["state"] in ("placed", "to_place")
    )
    assert placed["progress"]["state"] == "placed", placed
    book = (
        f"/data/files/ebooks/Shelfdrop Author/{series}/02 - Le Second Livre/"
        f"{series} - T02 - Le Second Livre.epub"
    )
    assert stack.exec_placement("cat", book).stdout == "epub"
