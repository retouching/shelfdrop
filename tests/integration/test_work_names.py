"""The languages of the names of a work through the real API: a name in a language not searched
by default, or in none known, is shown but unchecked (tests/unit/works/cases.py)."""

import httpx
import pytest

from tests.unit.works.cases import CASES, Case

pytestmark = [pytest.mark.works, pytest.mark.works_names_language]

SEARCHED_LANGUAGES = frozenset({"fr", "en", "ja-ro", "release"})
WITH_UNCHECKED = [case for case in CASES if case.unchecked]


@pytest.mark.parametrize("case", WITH_UNCHECKED, ids=[case.slug for case in WITH_UNCHECKED])
def test_a_name_in_another_language_is_shown_unchecked(client: httpx.Client, case: Case) -> None:
    body = client.get("/api/v1/works", params={"q": case.query, "kind": case.kind}).json()

    names = {name["title"]: name for name in body["works"][0]["names"]}
    for title in case.unchecked:
        assert title in names
        assert names[title]["checked"] is False


@pytest.mark.parametrize("case", CASES, ids=[case.slug for case in CASES])
def test_a_checked_name_is_in_a_searched_language_or_the_title(
    client: httpx.Client, case: Case
) -> None:
    body = client.get("/api/v1/works", params={"q": case.query, "kind": case.kind}).json()

    first = body["works"][0]
    for name in first["names"]:
        if name["checked"]:
            assert name["language"] in SEARCHED_LANGUAGES or name["title"] == first["title"]


@pytest.mark.parametrize("case", CASES, ids=[case.slug for case in CASES])
def test_each_name_keeps_the_sources_that_gave_it(client: httpx.Client, case: Case) -> None:
    body = client.get("/api/v1/works", params={"q": case.query, "kind": case.kind}).json()

    first = body["works"][0]
    for name in first["names"]:
        assert name["sources"], name["title"]
        assert set(name["sources"]) <= set(first["sources"])
        assert name["source"] == name["sources"][0]
