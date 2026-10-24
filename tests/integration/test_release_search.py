"""The search of the releases of a work through the real API, Prowlarr played by the fake
sources: one request per name, the releases kept once, set aside, their volumes,
their order."""

import httpx
import pytest

from tests.integration.support import FakeSources, prowlarr_search_stub, run_search

pytestmark = [pytest.mark.releases, pytest.mark.releases_search]


def test_a_work_is_searched_under_each_name_in_its_category(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    body = run_search(
        client,
        {
            "mode": "work",
            "kind": "manga",
            "title": "Jujutsu Kaisen",
            "names": ["Jujutsu Kaisen", "Sorcery Fight"],
        },
    )

    assert body["progress"]["state"] == "done"
    assert [n["name"] for n in body["progress"]["names"]] == ["Jujutsu Kaisen", "Sorcery Fight"]
    for name in ("Jujutsu Kaisen", "Sorcery Fight"):
        [params] = fake_sources.prowlarr_searches(name)[-1:]
        assert params["categories"] == ["7030"]
    titles = [r["title"] for r in body["releases"]]
    # Packs first, then volume by volume; T01 once (same infohash on two trackers, and found
    # by both names); T25 has no seed.
    assert titles[0].startswith("Jujutsu Kaisen (01-26)")
    assert body["releases"][0]["volumes"] == {"kind": "range", "first": 1, "last": 26}
    assert sum("Jujutsu.Kaisen.T01.FRENCH.MANGA" in t for t in titles) == 1
    assert not any(".T25." in t for t in titles)
    sorcery = next(r for r in body["releases"] if r["title"].startswith("Sorcery Fight"))
    assert sorcery["matched_name"] == "Sorcery Fight"
    assert sorcery["volumes"] == {"kind": "single", "first": 4, "last": 4}
    firsts = [r["volumes"]["first"] for r in body["releases"][1:]]
    assert firsts == sorted(firsts)
    assert "downloadUrl" not in str(body)
    assert "apikey" not in str(body)


def test_dusk_maiden_does_not_bring_amnesia(client: httpx.Client) -> None:
    """The 21/10 mistake: a release that misses a word of its name is set aside."""
    body = run_search(
        client,
        {
            "mode": "work",
            "kind": "manga",
            "title": "Dusk Maiden of Amnesia",
            "names": ["Dusk Maiden of Amnesia", "Tasogare Otome × Amnesia"],
        },
    )

    rejected = {r["title"]: r["rejected"] for r in body["releases"]}
    assert rejected["Amnesia.T01.FRENCH.CBZ.eBook-NOTAG"] == "relevance"
    assert rejected["Tasogare.Otome.x.Amnesia.T01.FRENCH.CBZ.eBook-PapriKa+"] is None
    assert rejected["Dusk Maiden of Amnesia (01-10) (Maybe) [Digital] (PapriKa+)"] is None


def test_an_audiobook_is_searched_in_the_audiobook_category(
    client: httpx.Client, fake_sources: FakeSources
) -> None:
    body = run_search(
        client,
        {
            "mode": "work",
            "kind": "audiobook",
            "title": "Les aventuriers de la mer",
            "names": ["Les aventuriers de la mer"],
        },
    )

    assert fake_sources.prowlarr_searches("Les aventuriers de la mer")[-1]["categories"] == ["3030"]
    assert body["releases"][0]["title"].endswith("Kuppit")


def test_a_name_is_cleaned_before_prowlarr(client: httpx.Client, fake_sources: FakeSources) -> None:
    run_search(
        client,
        {
            "mode": "work",
            "kind": "manga",
            "title": "Kaguya",
            "names": ['Kaguya-sama: "Love" is War!'],
        },
    )

    assert fake_sources.prowlarr_searches("Kaguya-sama Love is War")


def test_a_work_is_searched_under_6_names_at_most(client: httpx.Client) -> None:
    response = client.post(
        "/api/v1/searches",
        json={
            "mode": "work",
            "kind": "manga",
            "title": "x",
            "names": [f"Name number {i}" for i in range(7)],
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "too_many_names"


def test_prowlarr_failing_fails_the_search(client: httpx.Client, fake_sources: FakeSources) -> None:
    stub = prowlarr_search_stub("prowlarr down 5c1a", [7030], [])
    stub["response"] = {"status": 500}
    fake_sources.load([stub])

    body = run_search(
        client,
        {"mode": "work", "kind": "manga", "title": "x", "names": ["prowlarr down 5c1a"]},
    )

    assert body["progress"]["state"] == "failed"
    assert body["releases"] == []
