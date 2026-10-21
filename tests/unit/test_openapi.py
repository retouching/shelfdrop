"""shelfdrop.openapi: docs/openapi.json is the document of the application as it is."""

from shelfdrop.openapi import OPENAPI_FILE, document
from tests.unit.test_layers import ROOT


def test_the_committed_document_is_up_to_date() -> None:
    committed = (ROOT / OPENAPI_FILE).read_text(encoding="utf-8")

    assert committed == document(), "run `uv run python -m shelfdrop.openapi` and commit"
