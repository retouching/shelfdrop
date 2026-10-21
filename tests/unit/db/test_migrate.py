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
