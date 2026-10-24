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
    "e24f8ad607d1": "baf850d1c66429764e0b752aa3ab53153141795a81d73c44b79fa17a1f058c44",
    "45c8bccac8e0": "a149f4f2f4f6a095ac3a1512d3eb8d48089104dbe07fbe831eedeec4d3f815b9",
    "1170143ab2d3": "6f3a4dd918629dd6e60b796245c38ea48ba5d81067f0c559e63ed64d7267823d",
    "cd0744c2d266": "e1f922034ca153a6b7b383807b7d117675bb05837587ed9ba550577f6cbdf605",
    "06e04acd80d1": "f17279569570293b11cfd5de4d7f25b48fa558da75f51bb2bf6f940ecabb99d2",
    "7841e402f749": "d845241c1c427bbdb74e4fdfe0da17963125fdc17ea8ff11326860e7ae55759b",
    "fbd3a6ccd5f7": "9ac2d994ca3e37a7d626c1e0d341ee3b62889d3f87a524b4405335c127f4dd03",
    "36a54aec2e2c": "c9cb9f28979a3014c3e12216c1cac317c58cfbe0b2240b1104a068e76e6fa252",
    "b1c027fe08ea": "21c3388b9b751861cec4bbf80206fffde1285cf33811cf861d8e5f737da55466",
    "d28ca6c7c890": "c7959702f355e724b2a3b02e18cf9622438fe69f57d69ef1143a46acc16b08d5",
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
