"""The pictures shelfdrop takes (a cover, an image of a series): JPEG, PNG or WebP, known by their
first bytes."""

from typing import Final

PICTURES: Final = ((b"\xff\xd8\xff", "jpg", "image/jpeg"), (b"\x89PNG", "png", "image/png"))


def picture_of(data: bytes) -> tuple[str, str] | None:
    """The extension and the type of a JPEG, a PNG or a WebP picture; None for anything else."""
    for magic, extension, content_type in PICTURES:
        if data.startswith(magic):
            return extension, content_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None
