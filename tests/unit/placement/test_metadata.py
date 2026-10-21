"""shelfdrop.placement.metadata: the name, the series, the number and the authors of a file
placed, set and locked in Jellyfin."""

from shelfdrop.placement.metadata import locked_item
from shelfdrop.placement.types import ShelfFile


def shelf_file(path: str, volume: int | None, chapter: float | None = None) -> ShelfFile:
    return ShelfFile(
        id=1,
        kind="manga",
        work_id=None,
        series="Chainsaw Man",
        author="Tatsuki Fujimoto",
        volume=volume,
        chapter=chapter,
        path=path,
        locked=False,
        created_at=0,
    )


def test_a_volume_gets_its_name_its_series_its_number_and_its_author_locked() -> None:
    body = {"Id": "b1", "Name": "Tome 1", "LockedFields": ["Overview"], "Tags": ["x"]}

    item = locked_item(body, shelf_file("/s/Chainsaw Man/Chainsaw Man - T01.cbz", 1), [1])

    assert item["Name"] == item["SortName"] == item["ForcedSortName"] == "Chainsaw Man - T01"
    assert item["SeriesName"] == "Chainsaw Man"
    assert item["IndexNumber"] == 1
    assert item["People"] == [{"Name": "Tatsuki Fujimoto", "Type": "Author", "Role": ""}]
    assert item["LockedFields"] == ["Cast", "Name", "Overview"]
    # The rest of the item goes back as it was read.
    assert item["Tags"] == ["x"]


def test_a_chapter_alone_sorts_after_the_volumes_before_it_and_keeps_its_people() -> None:
    people = [{"Name": "Fujimoto", "Type": "Author"}]
    body = {"Id": "c1", "People": people}

    item = locked_item(
        body, shelf_file("/s/Chainsaw Man - T23 - Ch. 206.cbz", 23, 206), [1, 2, 22, 24]
    )

    assert item["Name"] == "Chainsaw Man - T23 - Ch. 206"
    assert item["ForcedSortName"] == "Chainsaw Man - T22 ~ 0206.0"
    assert "IndexNumber" not in item
    assert item["People"] == people
