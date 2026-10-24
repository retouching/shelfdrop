"""shelfdrop.placement.shelf: the one way a file goes on the shelf, a hardlink or a copy
(`placement.mode`), and nothing replaced."""

import errno
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import IO

import pytest

from shelfdrop.placement.shelf import (
    CopyFailedError,
    LinkRefusedError,
    moving_mode,
    place_file,
)
from shelfdrop.placement.types import PlaceMode

REAL_LINK = os.link


def refusing(source: Path, code: int = errno.EXDEV) -> Callable[..., None]:
    """`os.link` refused for `source` alone, as across two file systems."""

    def link(src: object, dst: object, *args: object, **kwargs: object) -> None:
        if Path(str(src)) == source:
            raise OSError(code, os.strerror(code))
        REAL_LINK(str(src), str(dst))

    return link


def torrent_file(tmp_path: Path, data: bytes = b"volume") -> Path:
    source = tmp_path / "torrents" / "Berserk T41.cbz"
    source.parent.mkdir(parents=True)
    source.write_bytes(data)
    (tmp_path / "shelf").mkdir()
    return source


def test_a_hardlink_shares_the_inode_of_the_torrent(tmp_path: Path) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"

    assert place_file(source, target, "hardlink") == "linked"
    assert os.stat(target).st_ino == os.stat(source).st_ino


@pytest.mark.parametrize("mode", ["hardlink", "hardlink_or_copy", "copy"])
def test_a_file_there_is_never_replaced(tmp_path: Path, mode: PlaceMode) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"
    target.write_bytes(b"mine")

    assert place_file(source, target, mode) == "exists"
    assert target.read_bytes() == b"mine"
    assert sorted(p.name for p in target.parent.iterdir()) == ["Berserk - T41.cbz"]


def test_a_link_refused_in_hardlink_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"
    monkeypatch.setattr(os, "link", refusing(source))

    with pytest.raises(LinkRefusedError, match="EXDEV"):
        place_file(source, target, "hardlink")
    assert not target.exists()


@pytest.mark.parametrize("code", [errno.EXDEV, errno.EPERM, errno.EACCES, errno.EMLINK])
def test_a_link_refused_in_hardlink_or_copy_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"
    monkeypatch.setattr(os, "link", refusing(source, code))

    assert place_file(source, target, "hardlink_or_copy") == "copied"
    assert target.read_bytes() == b"volume"
    assert os.stat(target).st_ino != os.stat(source).st_ino
    assert sorted(p.name for p in target.parent.iterdir()) == ["Berserk - T41.cbz"]


def test_hardlink_or_copy_links_when_it_can(tmp_path: Path) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"

    assert place_file(source, target, "hardlink_or_copy") == "linked"
    assert os.stat(target).st_ino == os.stat(source).st_ino


def test_copy_always_copies(tmp_path: Path) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"

    assert place_file(source, target, "copy") == "copied"
    assert target.read_bytes() == b"volume"
    assert os.stat(target).st_ino != os.stat(source).st_ino
    # The torrent keeps its file, untouched.
    assert source.read_bytes() == b"volume"
    assert os.stat(source).st_nlink == 1


def test_a_copy_cut_leaves_nothing_at_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = torrent_file(tmp_path, b"x" * 4096)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"

    def cut(read: IO[bytes], write: IO[bytes], length: int = 0) -> None:
        write.write(read.read(100))
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

    monkeypatch.setattr(shutil, "copyfileobj", cut)

    with pytest.raises(CopyFailedError, match="ENOSPC"):
        place_file(source, target, "copy")
    assert list(target.parent.iterdir()) == []


def test_a_copy_on_a_file_system_without_hardlinks_is_renamed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"

    def no_links(src: object, dst: object, *args: object, **kwargs: object) -> None:
        raise OSError(errno.EPERM, os.strerror(errno.EPERM))

    monkeypatch.setattr(os, "link", no_links)

    assert place_file(source, target, "copy") == "copied"
    assert target.read_bytes() == b"volume"
    assert sorted(p.name for p in target.parent.iterdir()) == ["Berserk - T41.cbz"]


def test_a_part_left_by_a_round_cut_is_written_again(tmp_path: Path) -> None:
    source = torrent_file(tmp_path)
    target = tmp_path / "shelf" / "Berserk - T41.cbz"
    (tmp_path / "shelf" / "Berserk - T41.cbz.part").write_bytes(b"half")

    assert place_file(source, target, "copy") == "copied"
    assert target.read_bytes() == b"volume"
    assert sorted(p.name for p in target.parent.iterdir()) == ["Berserk - T41.cbz"]


def test_a_file_moved_copies_only_when_its_link_is_refused() -> None:
    assert moving_mode("hardlink") == "hardlink"
    assert moving_mode("hardlink_or_copy") == "hardlink_or_copy"
    assert moving_mode("copy") == "hardlink_or_copy"
