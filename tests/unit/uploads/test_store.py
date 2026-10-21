import hashlib
from pathlib import Path

from shelfdrop.uploads.store import UploadStore


def test_the_chunks_are_put_together_in_their_order_and_go(tmp_path: Path) -> None:
    store = UploadStore(tmp_path / "uploads")
    store.write_chunk(4, 1, b"world")
    store.write_chunk(4, 0, b"hello ")

    digest = store.put_together(4, "Berserk T01.cbz", 2)

    assert digest == hashlib.sha256(b"hello world").hexdigest()
    assert store.file(4, "Berserk T01.cbz").read_bytes() == b"hello world"
    assert sorted(p.name for p in store.folder(4).iterdir()) == ["Berserk T01.cbz"]
    assert store.upload_ids() == [4]
    store.remove(4)
    assert store.upload_ids() == []


def test_a_chunk_sent_again_replaces_the_first(tmp_path: Path) -> None:
    store = UploadStore(tmp_path)
    store.write_chunk(1, 0, b"cut")
    store.write_chunk(1, 0, b"whole")

    assert store.chunk(1, 0).read_bytes() == b"whole"
    assert not store.chunk(1, 0).with_name("00000.part").exists()
