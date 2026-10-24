"""An audiobook in MP3 tracks (one a chapter) merged into one M4B with its chapters and its
cover, by the ffmpeg of the container.

The tracks are sorted by their number, one chapter each from its start to its end (their
lengths read by ffprobe), concatenated in AAC 96 kbit/s, `+faststart`, written into a `.part`
renamed once whole."""

import json
import logging
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

import anyio
import anyio.abc

logger = logging.getLogger(__name__)

FFMPEG: Final = "ffmpeg"
FFPROBE: Final = "ffprobe"
# A merge of 25 hours takes 10 to 15 minutes: no run of ffmpeg lasts more than this.
MERGE_SECONDS: Final = 3 * 3600
PROBE_SECONDS: Final = 60
FIRST_FRAME: Final = ("-frames:v", "1")


class AudioError(Exception):
    """ffprobe or ffmpeg failed, or gave no file."""


def chapters_metadata(title: str, durations: Sequence[float]) -> str:
    """The FFMETADATA of the M4B: its title, one chapter a track, 'Chapitre N', in
    milliseconds."""
    lines = [";FFMETADATA1", f"title={escape_metadata(title)}"]
    start = 0.0
    for index, duration in enumerate(durations, 1):
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={round(start * 1000)}",
            f"END={round((start + duration) * 1000)}",
            f"title=Chapitre {index}",
        ]
        start += duration
    return "\n".join(lines) + "\n"


def escape_metadata(value: str) -> str:
    """FFMETADATA escapes `=`, `;`, `#`, `\\` and the newline with a backslash."""
    for char in ("\\", "=", ";", "#", "\n"):
        value = value.replace(char, "\\" + char)
    return value


def concat_list(tracks: Sequence[Path]) -> str:
    """The list of the concat demuxer, each quote of a path escaped."""
    return "".join("file '" + str(t).replace("'", "'\\''") + "'\n" for t in tracks)


def merge_command(listing: Path, metadata: Path, cover: Path | None, part: Path) -> list[str]:
    """The ffmpeg command of a merge: the tracks, their chapters, the cover attached."""
    command = [FFMPEG, "-nostdin", "-y", "-v", "error", "-progress", "pipe:1"]
    command += ["-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(metadata)]
    if cover is not None:
        command += ["-i", str(cover), "-map", "0:a", "-map", "2:v", "-c:v", "copy"]
        command += ["-disposition:v", "attached_pic"]
    else:
        command += ["-map", "0:a"]
    command += ["-map_metadata", "1", "-map_chapters", "1", "-c:a", "aac", "-b:a", "96k"]
    command += ["-movflags", "+faststart", "-f", "mp4", str(part)]
    return command


def progress_of(line: str, total: float) -> int | None:
    """The percent of a merge from a line `out_time_us=` of `-progress`."""
    if not line.startswith("out_time_us=") or total <= 0:
        return None
    try:
        done = int(line.removeprefix("out_time_us=")) / 1_000_000
    except ValueError:
        return None
    return max(0, min(99, int(done * 100 / total)))


class AudioTools:
    """ffprobe and ffmpeg, run by the placement worker."""

    async def duration(self, track: Path) -> float:
        """Raises AudioError."""
        result = await self.run(
            [FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", str(track)],
            PROBE_SECONDS,
        )
        try:
            return float(json.loads(result)["format"]["duration"])
        except (ValueError, KeyError, TypeError) as exc:
            raise AudioError("no duration") from exc

    async def embedded_cover(self, track: Path, out: Path) -> bool:
        """The picture of the tags of a track (APIC) written to `out`; False without one."""
        picture = anyio.Path(out)
        try:
            await self.run(
                [
                    FFMPEG,
                    "-nostdin",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(track),
                    "-an",
                    *FIRST_FRAME,
                    str(out),
                ],
                PROBE_SECONDS,
            )
        except AudioError:
            await picture.unlink(missing_ok=True)
            return False
        return await picture.is_file() and (await picture.stat()).st_size > 0

    async def merge(
        self,
        tracks: Sequence[Path],
        title: str,
        cover: Path | None,
        out: Path,
        on_progress: Callable[[int], None],
    ) -> float:
        """The M4B `out` of `tracks`; its length in seconds. A file already at `out` is never
        replaced (FileExistsError). Raises AudioError."""
        target = anyio.Path(out)
        if await target.exists():
            raise FileExistsError(out)
        durations = [await self.duration(t) for t in tracks]
        total = sum(durations)
        part = anyio.Path(out.with_name(out.name + ".part"))
        with tempfile.TemporaryDirectory(prefix="shelfdrop-merge-") as work:
            listing = anyio.Path(work) / "concat.txt"
            metadata = anyio.Path(work) / "chapters.txt"
            await listing.write_text(concat_list(tracks), encoding="utf-8")
            await metadata.write_text(chapters_metadata(title, durations), encoding="utf-8")
            try:
                await self.run(
                    merge_command(Path(listing), Path(metadata), cover, Path(part)),
                    MERGE_SECONDS,
                    lambda line: report(line, total, on_progress),
                )
                if not await part.is_file():
                    raise AudioError("no file")
                if await target.exists():
                    raise FileExistsError(out)
                await part.rename(out)
            except BaseException:
                with anyio.CancelScope(shield=True):
                    await part.unlink(missing_ok=True)
                raise
        return total

    async def run(
        self, command: list[str], seconds: float, on_line: Callable[[str], None] | None = None
    ) -> str:
        """The output of `command`. Raises AudioError on a failure or past `seconds`."""
        lines: list[str] = []
        try:
            with anyio.fail_after(seconds):
                async with await anyio.open_process(command) as process:
                    await read_lines(process, lines, on_line)
                    code = await process.wait()
        except (OSError, TimeoutError) as exc:
            raise AudioError(type(exc).__name__) from exc
        if code != 0:
            logger.info("ffmpeg failed", extra={"code": code})
            raise AudioError(f"exit {code}")
        return "\n".join(lines)


def report(line: str, total: float, on_progress: Callable[[int], None]) -> None:
    percent = progress_of(line, total)
    if percent is not None:
        on_progress(percent)


async def read_lines(
    process: anyio.abc.Process, lines: list[str], on_line: Callable[[str], None] | None
) -> None:
    """The output of `process`, line by line; its errors are read to the end and dropped."""

    async def drain() -> None:
        if process.stderr is not None:
            async for _ in process.stderr:
                pass

    async with anyio.create_task_group() as group:
        group.start_soon(drain)
        if process.stdout is not None:
            buffer = b""
            async for chunk in process.stdout:
                buffer += chunk
                *complete, buffer = buffer.split(b"\n")
                for raw in complete:
                    line = raw.decode(errors="replace").strip()
                    lines.append(line)
                    if on_line is not None:
                        on_line(line)
            if buffer:
                lines.append(buffer.decode(errors="replace").strip())
