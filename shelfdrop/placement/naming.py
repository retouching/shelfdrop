"""The names of the shelf, as the scripts before shelfdrop wrote them: a
volume of manga `<Series> - TXX.<ext>` in the folder of its series, a book
`<Author>/<Series>/<NN - Title>/<Series> - TNN - <Title>.<ext>`, a chapter placed alone
`<Series> - T23 - Ch. 206` or `<Series> - Ch. 230`. Pure: no I/O."""

import re
from typing import Final

from shelfdrop.releases.guess import volumes_of

# Characters no folder of the libraries may hold (Windows clients of Jellyfin read them too).
UNSAFE: Final = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
# The extensions of what the shelf holds.
COMIC_EXTENSIONS: Final = (".cbz", ".cbr", ".cb7", ".pdf", ".epub", ".zip")
EBOOK_EXTENSIONS: Final = (".epub", ".pdf", ".mobi", ".azw3", ".cbz")
AUDIO_EXTENSIONS: Final = (".m4b", ".m4a", ".mp3", ".flac", ".opus", ".ogg", ".aac")
IMAGE_EXTENSIONS: Final = (".jpg", ".jpeg", ".png", ".webp")
# The dashes around a title: a hyphen, an en dash.
DASHES: Final = " -\u2013"
# What ends the title of a volume in the name of a release: a tag, a year, a format.
TITLE_END: Final = re.compile(
    r"(?<![A-Za-z])(?:FRENCH|MULTI|VFF?|TRUEFRENCH|EPUB|PDF|MOBI|AZW3|CBZ|CBR|MP3|M4B|"
    r"AAC|FLAC|WEB|AUDIOBOOK|LIVRE\s?AUDIO|eBook|NOTAG|(?:19|20)\d\d)(?![A-Za-z])",
    re.IGNORECASE,
)
# A volume number in a file name: "T12", "Tome 12", "Vol.12",
# "v12", "... 12.cbz"; the range of a pack, "(01-23)", is no volume.
FILE_VOLUME: Final = (
    re.compile(r"(?:^|[ ._\-\[(])T(\d{1,3})(?=$|[ ._\-\])])", re.IGNORECASE),
    re.compile(r"Tome[ ._]?(\d{1,3})", re.IGNORECASE),
    re.compile(r"(?:^|[ ._\-])(?:Vol(?:ume)?\.?|v)[ ._]?(\d{1,3})(?=$|[ ._\-])", re.IGNORECASE),
    re.compile(r"[ ._\-](\d{1,3})$"),
)


def safe(name: str) -> str:
    """A name a folder or a file of the shelf may take: no separator, no control character,
    no dot at its ends, spaces reduced."""
    cleaned = " ".join(UNSAFE.sub(" ", name).split()).strip(" .")
    return cleaned[:150] or "_"


def volume_label(number: int) -> str:
    return f"T{number:02d}"


def comic_name(series: str, volume: int, extension: str) -> str:
    """'Chainsaw Man - T01.cbz'."""
    return f"{safe(series)} - {volume_label(volume)}{extension.lower()}"


def chapter_label(chapter: float) -> str:
    """'206', '12.5'."""
    return f"{chapter:g}"


def chapter_name(
    series: str, volume: int | None, chapter: float, extension: str, last: float | None = None
) -> str:
    """'Chainsaw Man - T23 - Ch. 206.cbz' (a chapter of a volume not complete), 'Chainsaw Man -
    Ch. 230.cbz' (a chapter of no volume yet), 'Chainsaw Man - Ch. 233-236.cbz' (a file of
    several chapters, `last`)."""
    within = "" if volume is None else f" - {volume_label(volume)}"
    numbers = chapter_label(chapter)
    if last is not None and last > chapter:
        numbers += f"-{chapter_label(last)}"
    return f"{safe(series)}{within} - Ch. {numbers}{extension.lower()}"


def chapter_sort_name(series: str, after: int | None, chapter: float) -> str:
    """The `SortName` of a chapter placed alone: after the volume `after` (the last one before
    it, None before the first), before the next one, in the order of the chapters (`.5`
    too). 'Chainsaw Man - T22 ~ 0230.0' sorts after 'Chainsaw Man - T22' and before
    'Chainsaw Man - T23'."""
    volume = "T00" if after is None else volume_label(after)
    return f"{safe(series)} - {volume} ~ {chapter:06.1f}"


def book_folder(author: str, series: str, volume: int, title: str) -> tuple[str, str, str]:
    """The three folders of a book: ('Robin Hobb', 'Les Aventuriers de la mer', '01 - Le
    Vaisseau magique')."""
    return safe(author), safe(series), f"{volume:02d} - {safe(title)}"


def book_name(series: str, volume: int, title: str, extension: str, track: int | None) -> str:
    """'Les Aventuriers de la mer - T01 - Le Vaisseau magique.epub', with ' - 001' for a track."""
    base = f"{safe(series)} - {volume_label(volume)} - {safe(title)}"
    return base + ("" if track is None else f" - {track:03d}") + extension.lower()


def file_volume(stem: str) -> int | None:
    """The volume a file name gives; None without one."""
    text = re.sub(r"\(\d{1,3}-\d{1,3}\)", "", stem)
    text = re.sub(r"\[[^\]]*\]|\((?:19|20)\d\d\)", "", text).strip()
    for pattern in FILE_VOLUME:
        found = pattern.search(text)
        if found is not None:
            return int(found.group(1))
    single = volumes_of(text)
    return single.first if single.kind == "single" else None


def stated_volume(name: str) -> int | None:
    """A volume a name states ('T02', 'Tome 2', 'Vol.2'), never a bare number (the number of a
    chapter, or the track of an audiobook)."""
    for pattern in FILE_VOLUME[:3]:
        found = pattern.search(name)
        if found is not None:
            return int(found.group(1))
    return None


def volume_title(release: str, volume: int | None, series: str) -> str:
    """The title of a volume read in the name of its release, after its number and before
    its tags ('Les.Aventuriers.de.la.mer.01.Le.Vaisseau.magique.2001.FRENCH.MP3' -> 'Le Vaisseau
    magique'); the series without one."""
    text = re.sub(r"[._]+", " ", release)
    if volume is not None:
        found = re.search(rf"(?<![0-9])(?:T|Tome\s?)?0*{volume}(?![0-9])", text, re.IGNORECASE)
        if found is not None:
            after = text[found.end() :]
            end = TITLE_END.search(after)
            title = (after[: end.start()] if end else after).strip(DASHES)
            title = re.sub(r"\s*[\[(].*$", "", title).strip(DASHES)
            if len(title) >= 2 and not title.isdigit():
                return title
    return series
