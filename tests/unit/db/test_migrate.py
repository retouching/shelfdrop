"""The chain of the Alembic revisions (ADR 0005)."""

import hashlib
from pathlib import Path
from typing import Final

from alembic.config import Config
from alembic.script import ScriptDirectory

from shelfdrop.db.migrate import MIGRATIONS_DIR

BASE: Final = "e9ad2f300034"
# The sha256 of the file of every pushed revision. A new revision adds its line in its commit;
# a line that exists never changes: a pushed revision is never edited (ADR 0005).
DIGESTS: Final = {
    "e9ad2f300034": "2f8743bd937e7eaa2eafd9b394741210f2da3d4d62c2da801ee5aa6621479c88",
    "c7d1d70b5ae2": "832099d1b77a33603f019acc07d32b3de7e8e6ed6c109161410219b15a45cdbd",
    "eab842edd711": "5639c2a33ea4c8c18d3c01ea6858cbaa716d59f0d48419321d27190b611c3bc9",
    "568e93e7e2dc": "b704cd5399defa8df3c5bbb957bb5cbf3fa6c9984b9d9afc927d40cefb7e5fe0",
    "e88f18e15668": "a5456acb90f31a8cef43de6763059a19be0240deb50960cc9a1f33f74913e013",
    "a250a56263cc": "bed6836cf90ab29b248ae1aff74e5b59fd59ce30a82564d704295963add92165",
    "736da4d17972": "b61ff1f51a9cec3a092f488019511985e32a0ed8f1d7f7020ed1ec366ddb11d7",
    "13745d9b70d2": "73428b2de8528fdc77a8d26e2aa59e2b8d8848744c338692aafe2665e9dcec74",
}


def read_script() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(config)


def test_the_chain_starts_at_the_first_revision() -> None:
    assert read_script().get_bases() == [BASE]


def test_the_chain_has_one_head() -> None:
    assert len(read_script().get_heads()) == 1


def test_no_pushed_revision_changed() -> None:
    found = {
        revision.revision: hashlib.sha256(Path(revision.path).read_bytes()).hexdigest()
        for revision in read_script().walk_revisions()
    }

    assert found == DIGESTS
