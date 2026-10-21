"""Works merged by hand through the real API (plan section 3, point 9): two works of a recorded
search joined under the name chosen, kept for the next searches and read by their id, then
split; the merge undone is not found again."""

import httpx
import pytest

pytestmark = [pytest.mark.works, pytest.mark.works_merge]

# The works of this search the BnF knows stay the first three once two are merged: the merge
# asks the fake sources nothing they were not recorded with.
QUERY = {"q": "La Mémoire des os", "kind": "audiobook"}


def test_works_merged_by_hand_are_one_in_the_next_searches_until_split(
    client: httpx.Client,
) -> None:
    before = client.get("/api/v1/works", params=QUERY).json()["works"]
    first, second = before[0], before[3]
    assert first["merge_id"] is None
    assert first["parts"] == []

    created = client.post(
        "/api/v1/works/merges",
        json={
            "kind": "audiobook",
            "work_ids": [first["id"], second["id"]],
            "shelf_name": "La Mémoire des os (fusion)",
        },
    )
    assert created.status_code == 201, created.text
    merge = created.json()
    try:
        after = client.get("/api/v1/works", params=QUERY).json()["works"]
        [merged] = [w for w in after if w["merge_id"] == merge["id"]]
        assert len(after) == len(before) - 1
        assert merged["shelf_name"] == "La Mémoire des os (fusion)"
        assert merged["id"] == first["id"]
        assert [p["id"] for p in merged["parts"]] == [first["id"], second["id"]]
        assert [p["title"] for p in merged["parts"]] == [first["shelf_name"], second["shelf_name"]]
        assert all(w["id"] != second["id"] for w in after)
        assert set(first["sources"]) | set(second["sources"]) == set(merged["sources"])
        assert client.get(f"/api/v1/works/{merged['id']}").json() == merged
    finally:
        split = client.delete(f"/api/v1/works/merges/{merge['id']}")
    assert split.status_code == 204

    again = client.get("/api/v1/works", params=QUERY).json()["works"]
    assert [w["id"] for w in again] == [w["id"] for w in before]
    gone = client.delete(f"/api/v1/works/merges/{merge['id']}")
    assert (gone.status_code, gone.json()["code"]) == (404, "work_merge_not_found")


def test_a_merge_needs_two_works_found_and_a_name(client: httpx.Client) -> None:
    [work, *_] = client.get("/api/v1/works", params=QUERY).json()["works"]

    unknown = client.post(
        "/api/v1/works/merges",
        json={"kind": "audiobook", "work_ids": [work["id"], "kitsu:0"], "shelf_name": "X"},
    )
    alone = client.post(
        "/api/v1/works/merges",
        json={"kind": "audiobook", "work_ids": [work["id"], work["id"]], "shelf_name": "X"},
    )
    blank = client.post(
        "/api/v1/works/merges",
        json={"kind": "audiobook", "work_ids": [work["id"], "kitsu:0"], "shelf_name": "  "},
    )

    assert (unknown.status_code, unknown.json()["code"]) == (404, "work_not_found")
    assert (alone.status_code, alone.json()["code"]) == (422, "work_merge_refused")
    assert (blank.status_code, blank.json()["code"]) == (422, "work_merge_refused")
