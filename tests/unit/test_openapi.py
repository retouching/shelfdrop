"""shelfdrop.openapi: docs/openapi.json and docs/openapi.public.json are the documents of the
application as it is."""

from pathlib import Path

import pytest

from shelfdrop.openapi import OPENAPI_FILE, PUBLIC_OPENAPI_FILE, documents
from tests.unit.test_layers import ROOT


@pytest.mark.parametrize("path", [OPENAPI_FILE, PUBLIC_OPENAPI_FILE])
def test_the_committed_documents_are_up_to_date(path: Path) -> None:
    committed = (ROOT / path).read_text(encoding="utf-8")

    assert committed == documents()[path], "run `uv run python -m shelfdrop.openapi` and commit"
