"""shelfdrop.utils.torrent: the id of a torrent, from its file or its magnet link."""

import hashlib

from shelfdrop.utils.torrent import magnet_id, torrent_id
from tests.unit.support import bencode, torrent_file


def info_of(name: str) -> bytes:
    """The bencoded `info` of `torrent_file(name)`, as the test writes it again."""
    return bencode({"name": name, "length": 1024, "piece length": 16384, "pieces": b"\x01" * 20})


def test_the_id_is_the_sha1_of_the_info_dictionary() -> None:
    data = torrent_file("Berserk T01.cbz")

    assert (
        torrent_id(data)
        == hashlib.sha1(info_of("Berserk T01.cbz"), usedforsecurity=False).hexdigest()
    )
    assert torrent_id(torrent_file("Berserk T02.cbz")) != torrent_id(data)


def test_a_torrent_of_bittorrent_v2_is_named_by_its_sha256_cut_to_20_bytes() -> None:
    data = torrent_file("Berserk T01.cbz", v2=True)
    start = data.index(b"4:infod") + len(b"4:info")
    info = data[start:-1]

    assert torrent_id(data) == hashlib.sha256(info).hexdigest()[:40]


def test_what_is_not_a_torrent_has_no_id() -> None:
    assert torrent_id(b"") is None
    assert torrent_id(b"<html>Not found</html>") is None
    assert torrent_id(bencode({"announce": "x"})) is None
    assert torrent_id(torrent_file("x")[:-3]) is None
    assert torrent_id(torrent_file("x") + b"garbage") is None
    assert torrent_id(b"l" * 10_000) is None
    assert torrent_id(bencode({"info": [1, 2]})) is None


def test_a_magnet_link_gives_its_hash_in_hex_or_base32_and_its_v2_hash_first() -> None:
    v1 = "c12fe1c06bba254a9dc9f519b335aa7c1367a88a"
    base32 = "YEX6DQDLXISUVHOJ6UM3GNNKPQJWPKEK"
    v2 = "a" * 64

    assert magnet_id(f"magnet:?xt=urn:btih:{v1.upper()}&dn=Berserk") == v1
    assert magnet_id(f"magnet:?xt=urn:btih:{base32}") == v1
    assert magnet_id(f"magnet:?xt=urn:btih:{v1}&xt=urn:btmh:1220{v2}") == v2[:40]
    assert magnet_id("magnet:?dn=Berserk") is None
    assert magnet_id("https://example.org/a.torrent") is None
    assert magnet_id("magnet:?xt=urn:btih:1234") is None
