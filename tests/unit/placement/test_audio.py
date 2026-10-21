"""shelfdrop.placement.audio: the chapters of an M4B, the command of ffmpeg, its progress (the
merge itself runs ffmpeg in the image: tests/integration/test_placement_audio.py)."""

from pathlib import Path

from shelfdrop.placement.audio import (
    chapters_metadata,
    concat_list,
    merge_command,
    progress_of,
)


def test_each_track_is_a_chapter_from_its_start_to_its_end() -> None:
    metadata = chapters_metadata("Le dragon et l'oiseau", [61.5, 120.25])

    assert metadata == (
        ";FFMETADATA1\n"
        "title=Le dragon et l'oiseau\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=61500\ntitle=Chapitre 1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=61500\nEND=181750\ntitle=Chapitre 2\n"
    )
    assert "title=a\\=b\\;c" in chapters_metadata("a=b;c", [])


def test_the_list_of_the_tracks_escapes_their_quotes() -> None:
    assert concat_list([Path("/b/l'oiseau - 001.mp3")]) == "file '/b/l'\\''oiseau - 001.mp3'\n"


def test_the_merge_is_aac_at_96_kbits_faststart_with_its_cover_attached() -> None:
    command = merge_command(Path("l.txt"), Path("m.txt"), Path("cover.jpg"), Path("out.m4b.part"))

    joined = " ".join(command)
    assert "-c:a aac -b:a 96k" in joined
    assert "-movflags +faststart -f mp4 out.m4b.part" in joined
    assert "-map 2:v -c:v copy -disposition:v attached_pic" in joined
    assert "-map_chapters 1" in joined
    assert "attached_pic" not in " ".join(merge_command(Path("l"), Path("m"), None, Path("o")))


def test_the_progress_is_read_from_the_time_written() -> None:
    assert progress_of("out_time_us=45000000", 90.0) == 50
    assert progress_of("out_time_us=95000000", 90.0) == 99
    assert progress_of("speed=12x", 90.0) is None
    assert progress_of("out_time_us=N/A", 90.0) is None
