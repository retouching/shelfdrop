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
