"""The work search through the real API, the fake sources replaying the exchanges recorded from
the real ones: what each search must find is the contract of tests/unit/works/cases.py."""

import httpx
import pytest

from tests.integration.support import FakeSources
from tests.unit.works.cases import CASES, Case

pytestmark = [pytest.mark.works, pytest.mark.works_search]


@pytest.mark.parametrize("case", CASES, ids=[case.slug for case in CASES])
def test_a_recorded_search(client: httpx.Client, fake_sources: FakeSources, case: Case) -> None:
    response = client.get("/api/v1/works", params={"q": case.query, "kind": case.kind})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == case.query
    assert body["kind"] == case.kind
    first = body["works"][0]
    assert first["shelf_name"] == case.shelf_name
    checked = {name["title"] for name in first["names"] if name["checked"]}
    assert set(case.names) <= checked
    if case.author:
        assert case.author in first["authors"]
    if case.volumes:
        assert first["volumes"] == case.volumes
    if case.volumes_fr:
        assert first["volumes_fr"] == case.volumes_fr
    assert first["shelf_name"] not in case.not_first
    assert len([name for name in first["names"] if name["checked"]]) <= 6


def test_every_request_of_the_searches_was_recorded(fake_sources: FakeSources) -> None:
    """After the searches above: none asked the fake something it was not recorded with."""
    assert fake_sources.unmatched() == []


def test_a_manga_search_puts_the_other_forms_apart(client: httpx.Client) -> None:
    body = client.get("/api/v1/works", params={"q": "Chainsaw Man", "kind": "manga"}).json()

    assert all(work["form"] not in ("novel", "anthology", "doujinshi") for work in body["works"])
    assert any(work["form"] in ("novel", "doujinshi") for work in body["other_forms"])


def test_dusk_maiden_is_not_amnesia(client: httpx.Client) -> None:
    body = client.get(
        "/api/v1/works", params={"q": "Dusk Maiden of Amnesia", "kind": "manga"}
    ).json()

    first = body["works"][0]
    amnesia = [work for work in body["works"] if work["shelf_name"] == "Amnesia"]
    assert first["shelf_name"] == "Dusk Maiden of Amnesia"
    assert amnesia
    assert amnesia[0]["id"] != first["id"]


def test_a_work_found_is_read_by_its_id(client: httpx.Client) -> None:
    found = client.get("/api/v1/works", params={"q": "Berserk", "kind": "manga"}).json()
    work = found["works"][0]

    read = client.get(f"/api/v1/works/{work['id']}")

    assert read.status_code == 200
    assert read.json() == work
