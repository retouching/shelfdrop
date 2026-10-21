"""Torrents: the id a torrent client names a torrent by, read from a `.torrent` file (its
bencoded `info` dictionary) or from a magnet link.

The id is the SHA-1 of the bencoded `info` (BitTorrent v1), or, for a torrent of BitTorrent v2
(`meta version` 2, hybrid ones included), the first 20 bytes of its SHA-256, as libtorrent's
`info_hash_t::get_best()` gives it. In hex, lower case.
"""

import base64
import binascii
import hashlib
import re
from typing import Final
from urllib.parse import parse_qs

# A magnet link of BitTorrent v1 (`urn:btih:`: 40 hex or 32 base32) and of v2 (`urn:btmh:`:
# the multihash of a SHA-256, `1220` then 64 hex).
BTIH: Final = re.compile(r"^urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})$")
BTMH: Final = re.compile(r"^urn:btmh:1220([0-9a-fA-F]{64})$")
# Deeper than any real torrent: a guard against a file built to exhaust the stack.
MAX_DEPTH: Final = 64


class Malformed(ValueError):
    """Not bencoding; never leaves this module."""


def value_end(data: bytes, start: int, depth: int = 0) -> int:
    """Where the bencoded value at `start` ends. Raises Malformed."""
    if depth > MAX_DEPTH or start >= len(data):
        raise Malformed
    head = data[start : start + 1]
    if head == b"i":
        end = data.find(b"e", start)
        if end < 0 or not re.fullmatch(rb"-?\d+", data[start + 1 : end]):
            raise Malformed
        return end + 1
    if head in (b"l", b"d"):
        position = start + 1
        while data[position : position + 1] != b"e":
            if head == b"d" and not data[position : position + 1].isdigit():
                raise Malformed
            position = value_end(data, position, depth + 1)
            if head == b"d":
                position = value_end(data, position, depth + 1)
        return position + 1
    if head.isdigit():
        colon = data.find(b":", start)
        if colon < 0 or not data[start:colon].isdigit():
            raise Malformed
        end = colon + 1 + int(data[start:colon])
        if end > len(data):
            raise Malformed
        return end
    raise Malformed


def string_at(data: bytes, start: int) -> tuple[bytes, int]:
    """The byte string at `start` and where it ends. Raises Malformed."""
    end = value_end(data, start)
    if not data[start : start + 1].isdigit():
        raise Malformed
    return data[data.find(b":", start) + 1 : end], end


def dictionary_items(data: bytes, start: int) -> dict[bytes, tuple[int, int]]:
    """The keys of the dictionary at `start`, with where each value starts and ends."""
    if data[start : start + 1] != b"d":
        raise Malformed
    items: dict[bytes, tuple[int, int]] = {}
    position = start + 1
    while data[position : position + 1] != b"e":
        key, position = string_at(data, position)
        end = value_end(data, position)
        items[key] = (position, end)
        position = end
    return items


def torrent_id(data: bytes) -> str | None:
    """The id of a `.torrent` file, or None when it is not one."""
    try:
        if value_end(data, 0) != len(data):
            return None
        info = dictionary_items(data, 0).get(b"info")
        if info is None:
            return None
        encoded = data[info[0] : info[1]]
        fields = dictionary_items(encoded, 0)
    except Malformed:
        return None
    version = fields.get(b"meta version")
    if version is not None and encoded[version[0] : version[1]] == b"i2e":
        return hashlib.sha256(encoded).hexdigest()[:40]
    return hashlib.sha1(encoded, usedforsecurity=False).hexdigest()


def magnet_id(uri: str) -> str | None:
    """The id a magnet link names (its v2 hash first), or None when it names none."""
    if not uri.startswith("magnet:?"):
        return None
    topics = parse_qs(uri.removeprefix("magnet:?")).get("xt", [])
    for topic in topics:
        found = BTMH.match(topic)
        if found:
            return found.group(1)[:40].lower()
    for topic in topics:
        found = BTIH.match(topic)
        if found:
            value = found.group(1)
            if len(value) == 40:
                return value.lower()
            try:
                return base64.b32decode(value.upper()).hex()
            except binascii.Error:
                return None
    return None
