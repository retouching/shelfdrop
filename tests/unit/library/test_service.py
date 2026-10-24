"""LibraryService: the series of the libraries of Jellyfin, their proposals, their changes, the
summaries by batch and the scans, on the fake Jellyfin."""

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.library.exceptions import (
    ImageRefusedError,
    LibraryUnavailableError,
    SeriesNotFoundError,
    VolumeNotFoundError,
)
from shelfdrop.library.service import LibraryService, missing_numbers, series_folder
from shelfdrop.library.types import (
    ItemImage,
    LinkImage,
    ScanOrder,
    SentImage,
    SeriesChange,
    VolumeChange,
)
from shelfdrop.works.exceptions import NoSourceAnsweredError
from shelfdrop.works.types import Kind, Work, WorkSearch
from tests.unit.clients.support import API_KEY, FakeJellyfin
from tests.unit.placement.support import FakePlacementRepository, libraries_of
from tests.unit.works.support import FixedClock

JPEG = b"\xff\xd8\xff\xe0image"
# The refresh after a change: every provider, for what is empty alone; no image replaced (F40).
AFTER_CHANGE = {
    "recursive": "true",
    "metadataRefreshMode": "FullRefresh",
    "imageRefreshMode": "Default",
    "replaceAllMetadata": "false",
    "replaceAllImages": "false",
}
ROOTS: dict[Kind, str] = {
    "manga": "/data/files/comics",
    "ebook": "/data/files/ebooks",
    "audiobook": "/data/files/audiobooks",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def item(item_id: str, kind: str, path: str, library: str, **fields: Any) -> dict[str, Any]:
    return {
        "Id": item_id,
        "Type": kind,
        "Name": path.rsplit("/", 1)[-1],
        "Path": path,
        "LibraryId": library,
        **fields,
    }


def shelf() -> FakeJellyfin:
    """Berserk (2 volumes, one without a summary nor an image), a book under its author, and a
    file at the root of the comics."""
    comics = "/files/comics"
    items = [
        item(
            "berserk",
            "Folder",
            f"{comics}/Berserk",
            "lib-manga",
            Overview="Guts.",
            ImageTags={"Primary": "t"},
        ),
        item(
            "b1",
            "Book",
            f"{comics}/Berserk/Berserk - T01.cbz",
            "lib-manga",
            IndexNumber=1,
            Overview="T1",
            ImageTags={"Primary": "t"},
            People=[{"Name": "Kentaro Miura", "Type": "Author"}],
        ),
        item("b2", "Book", f"{comics}/Berserk/Berserk - T02.cbz", "lib-manga", IndexNumber=2),
        item("loose", "Book", f"{comics}/loose.cbz", "lib-manga"),
        item("hobb", "Folder", "/files/ebooks/Robin Hobb", "lib-ebook"),
        item("mer", "Folder", "/files/ebooks/Robin Hobb/Les Aventuriers de la mer", "lib-ebook"),
        item(
            "mer1",
            "Folder",
            "/files/ebooks/Robin Hobb/Les Aventuriers de la mer/01 - Le Vaisseau",
            "lib-ebook",
        ),
        item(
            "mer1b",
            "Book",
            "/files/ebooks/Robin Hobb/Les Aventuriers de la mer/01 - Le Vaisseau/x.epub",
            "lib-ebook",
        ),
    ]
    return FakeJellyfin(
        libraries=libraries_of(ROOTS),
        items={i["Id"]: i for i in items}
        | {f"lib-{k}": {"Id": f"lib-{k}", "Type": "CollectionFolder"} for k in ROOTS},
        images={"b1": JPEG},
        files={"b1": b"x" * 2048, "b2": b"y" * 10},
    )


@dataclass
class Settings:
    async def jellyfin(self) -> tuple[str | None, str | None]:
        return "http://jellyfin.test", API_KEY

    async def libraries(self) -> dict[Kind, str]:
        return dict(ROOTS)


@dataclass
class Works:
    found: list[Work] = field(default_factory=list)
    down: bool = False

    async def search(self, query: str, kind: Kind) -> WorkSearch:
        if self.down:
            raise NoSourceAnsweredError
        return WorkSearch(
            query=query, kind=kind, works=tuple(self.found), other_forms=(), unavailable=()
        )


@dataclass
class Images:
    async def image(self, url: str) -> bytes | None:
        return JPEG if url.endswith(".jpg") else None


def berserk_work() -> Work:
    return Work(
        id="mangaupdates:1",
        title="Berserk",
        shelf_name="Berserk",
        authors=(),
        year=None,
        volumes=None,
        volumes_fr=None,
        form="manga",
        names=(),
        sources=("mangaupdates", "kitsu"),
        cover_url=None,
        isbns=(),
        links={},
        covers={"kitsu": "https://media.kitsu.test/b.jpg"},
        summaries={"mangaupdates": "Guts, the Black Swordsman."},
    )


def service_of(
    jellyfin: FakeJellyfin, works: Works | None = None
) -> tuple[LibraryService, FakePlacementRepository]:
    repository = FakePlacementRepository()
    client = JellyfinClient(httpx.AsyncClient(transport=httpx.MockTransport(jellyfin)), "0.5.0")
    service = LibraryService(
        client, Settings(), works or Works(), Images(), lambda: repository, FixedClock()
    )
    return service, repository


def test_the_folder_of_a_series_is_its_first_folder_or_under_its_author() -> None:
    assert series_folder("/files/comics/Berserk/x.cbz", "/files/comics", "manga") == (
        "/files/comics/Berserk"
    )
    assert series_folder("/files/ebooks/A/S/01 - T/x.epub", "/files/ebooks", "ebook") == (
        "/files/ebooks/A/S"
    )
    assert series_folder("/files/ebooks/S/x.epub", "/files/ebooks", "ebook") == "/files/ebooks/S"
    assert series_folder("/files/comics/x.cbz", "/files/comics", "manga") is None
    assert series_folder("/other/x.cbz", "/files/comics", "manga") is None


@pytest.mark.anyio
async def test_the_series_are_the_folders_with_their_volumes_and_what_they_lack() -> None:
    service, _ = service_of(shelf())

    series = await service.read()

    assert [(s.id, s.kind, s.volumes) for s in series] == [
        ("berserk", "manga", 2),
        ("mer", "ebook", 1),
    ]
    berserk = series[0]
    assert berserk.has_image
    assert (berserk.volumes_without_summary, berserk.volumes_without_image) == (1, 1)
    # Its folder has no author: those of its volumes.
    assert berserk.authors == ("Kentaro Miura",)


@pytest.mark.anyio
async def test_the_proposals_are_the_volumes_then_the_sources() -> None:
    service, _ = service_of(shelf(), Works([berserk_work()]))

    proposals = await service.proposals("berserk")

    assert [(v.item_id, v.label, v.number, v.format) for v in proposals.volumes] == [
        ("b1", "Tome 1 \u00b7 CBZ", 1, "CBZ")
    ]
    assert [(c.source, c.url) for c in proposals.covers] == [
        ("kitsu", "https://media.kitsu.test/b.jpg")
    ]
    assert proposals.summaries[0].text == "Guts, the Black Swordsman."
    assert proposals.work_id == "mangaupdates:1"
    down, _ = service_of(shelf(), Works(down=True))
    assert (await down.proposals("berserk")).covers == ()
    with pytest.raises(SeriesNotFoundError):
        await service.proposals("b1")


def change(**fields: Any) -> SeriesChange:
    values: dict[str, Any] = {
        "name": "Berserk",
        "original_title": "ベルセルク",
        "authors": ("Kentaro Miura",),
        "year": 1990,
        "genres": ("Dark fantasy",),
        "summary": "Guts.",
        "lock": True,
        "summary_to_volumes": False,
        "image": None,
        "image_to_series": True,
        "image_to_volumes": False,
        "save_cover": False,
    }
    return SeriesChange(**(values | fields))


@pytest.mark.anyio
async def test_a_change_sets_and_locks_the_fields_and_copies_the_summary() -> None:
    jellyfin = shelf()
    jellyfin.items["berserk"]["People"] = [{"Name": "X", "Type": "Translator"}]
    service, _ = service_of(jellyfin)

    changed = await service.change(
        "berserk", change(summary="Le Guerrier noir.", summary_to_volumes=True)
    )

    series = jellyfin.items["berserk"]
    assert (series["Name"], series["OriginalTitle"], series["ProductionYear"]) == (
        "Berserk",
        "ベルセルク",
        1990,
    )
    assert series["People"] == [
        {"Name": "Kentaro Miura", "Type": "Author", "Role": ""},
        {"Name": "X", "Type": "Translator"},
    ]
    assert series["LockedFields"] == ["Cast", "Genres", "Name", "Overview"]
    # The volume without a summary gets it; the other keeps its own.
    assert jellyfin.items["b2"]["Overview"] == "Le Guerrier noir."
    assert jellyfin.items["b2"]["LockedFields"] == ["Overview"]
    assert jellyfin.items["b1"]["Overview"] == "T1"
    assert changed.volumes_without_summary == 0
    # Then its folder refreshed, never replacing what was written (F40).
    assert jellyfin.refreshed == [("berserk", AFTER_CHANGE)]


@pytest.mark.anyio
async def test_an_image_goes_to_the_series_the_volumes_without_one_and_the_worker() -> None:
    jellyfin = shelf()
    service, repository = service_of(jellyfin)

    await service.change(
        "berserk",
        change(image=ItemImage(item_id="b1"), image_to_volumes=True, save_cover=True, lock=False),
    )

    assert jellyfin.images["berserk"] == jellyfin.images["b2"] == JPEG
    [(task, state)] = repository.tasks.values()
    assert (task.kind, task.path, task.data, state) == (
        "cover",
        "/files/comics/Berserk",
        JPEG,
        "pending",
    )
    assert (
        "LockedFields" not in jellyfin.items["berserk"]
        or not jellyfin.items["berserk"]["LockedFields"]
    )


@pytest.mark.anyio
async def test_a_new_image_is_read_back_with_its_new_tag() -> None:
    jellyfin = shelf()
    service, _ = service_of(jellyfin)
    [before, *_] = await service.read()

    changed = await service.change("berserk", change(image=LinkImage(url="https://x.test/c.jpg")))
    volume = await service.change_volume(
        "b1", volume_change(image=LinkImage(url="https://x.test/c.jpg"))
    )

    assert before.image_tag == "t"
    assert changed.image_tag not in (None, "t")
    assert changed.image_tag == jellyfin.items["berserk"]["ImageTags"]["Primary"]
    assert volume.image_tag == jellyfin.items["b1"]["ImageTags"]["Primary"] != "t"
    proposals = await service.proposals("berserk")
    assert [(v.item_id, v.image_tag) for v in proposals.volumes] == [("b1", volume.image_tag)]


@pytest.mark.anyio
async def test_a_refresh_that_fails_after_a_change_never_fails_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    jellyfin = shelf()
    jellyfin.refresh_fails = True
    service, _ = service_of(jellyfin)

    changed = await service.change("berserk", change(name="Berserk Deluxe"))
    volume = await service.change_volume("b2", volume_change())

    assert (changed.name, volume.name) == ("Berserk Deluxe", "Berserk - T02 - Le Guerrier noir")
    assert jellyfin.refreshed == []
    failures = [r for r in caplog.records if r.message == "Jellyfin refresh after a change failed"]
    assert [getattr(r, "error", None) for r in failures] == ["ServiceError", "ServiceError"]


@pytest.mark.anyio
async def test_an_image_that_is_not_one_is_refused_before_any_change() -> None:
    jellyfin = shelf()
    service, _ = service_of(jellyfin)

    for image in (
        LinkImage(url="https://x.test/page.html"),
        SentImage(data=b"<svg/>"),
        ItemImage(item_id="b2"),
    ):
        with pytest.raises(ImageRefusedError):
            await service.change("berserk", change(name="Other", image=image))

    assert jellyfin.items["berserk"]["Name"] == "Berserk"
    # Nothing changed, nothing refreshed.
    assert jellyfin.refreshed == []
    await service.change("berserk", change(image=LinkImage(url="https://x.test/c.jpg")))
    assert jellyfin.images["berserk"] == JPEG


@pytest.mark.anyio
async def test_the_summaries_by_batch_go_where_there_is_none() -> None:
    jellyfin = shelf()
    service, _ = service_of(jellyfin)

    count = await service.fill({"berserk": "Le Guerrier noir.", "mer": "Les vivenefs.", "x": "?"})

    assert count == 2
    # Berserk keeps its own summary; its volume without one gets it.
    assert jellyfin.items["berserk"]["Overview"] == "Guts."
    assert jellyfin.items["b2"]["Overview"] == "Le Guerrier noir."
    assert jellyfin.items["mer"]["Overview"] == "Les vivenefs."
    assert jellyfin.items["mer"]["LockedFields"] == ["Overview"]


@pytest.mark.anyio
async def test_a_scan_targets_a_series_a_library_or_every_library() -> None:
    jellyfin = shelf()
    service, _ = service_of(jellyfin)

    await service.scan(ScanOrder(mode="missing", series_id="berserk"))
    await service.scan(ScanOrder(mode="all", kind="ebook"))
    await service.scan(ScanOrder(mode="new"))

    assert [(item_id, p.get("metadataRefreshMode")) for item_id, p in jellyfin.refreshed] == [
        ("berserk", "FullRefresh"),
        ("lib-ebook", "FullRefresh"),
        ("library", None),
    ]
    assert jellyfin.refreshed[1][1]["replaceAllMetadata"] == "true"
    assert await service.scanning() == {"manga": None, "ebook": None, "audiobook": None}


def test_the_numbers_missing_are_the_gaps_up_to_the_highest_held() -> None:
    assert missing_numbers([1, 2, 5, None, 2]) == (3, 4)
    assert missing_numbers([None]) == ()
    assert missing_numbers([]) == ()


@pytest.mark.anyio
async def test_the_volumes_of_a_series_come_with_their_file_and_the_numbers_missing() -> None:
    jellyfin = shelf()
    jellyfin.items["b4"] = item(
        "b4", "Book", "/files/comics/Berserk/Berserk - T04.cbz", "lib-manga"
    )
    service, _ = service_of(jellyfin)

    found = await service.volumes("berserk")

    assert found.series.id == "berserk"
    assert [(v.id, v.number, v.file_name, v.size) for v in found.volumes] == [
        ("b1", 1, "Berserk - T01.cbz", 2048),
        ("b2", 2, "Berserk - T02.cbz", 10),
        # No number in Jellyfin; its file says 4. Jellyfin has no file for it: no size.
        ("b4", None, "Berserk - T04.cbz", None),
    ]
    assert found.volumes[0].authors == ("Kentaro Miura",)
    assert found.volumes[0].has_image
    assert found.missing == (3,)
    with pytest.raises(SeriesNotFoundError):
        await service.volumes("b1")


@pytest.mark.anyio
async def test_the_file_of_a_volume_is_read_from_jellyfin_and_no_other_item() -> None:
    service, _ = service_of(shelf())

    found = await service.download("b1")
    data = b"".join([chunk async for chunk in found.file.chunks])

    assert (found.name, data, found.file.size) == ("Berserk - T01.cbz", b"x" * 2048, 2048)
    # A folder, a library, an unknown id: never asked of Jellyfin.
    for item_id in ("berserk", "lib-manga", "nope"):
        with pytest.raises(VolumeNotFoundError):
            await service.download(item_id)


@pytest.mark.anyio
async def test_a_volume_jellyfin_has_no_file_for_is_not_found_and_jellyfin_down_unavailable() -> (
    None
):
    jellyfin = shelf()
    service, _ = service_of(jellyfin)

    del jellyfin.files["b2"]
    with pytest.raises(VolumeNotFoundError):
        await service.download("b2")
    jellyfin.down = True
    with pytest.raises(LibraryUnavailableError):
        await service.download("b1")


def volume_change(**fields: Any) -> VolumeChange:
    values: dict[str, Any] = {
        "name": "Berserk - T02 - Le Guerrier noir",
        "number": 2,
        "summary": "Guts.",
        "authors": ("Kentaro Miura", "Studio Gaga"),
        "lock": True,
        "image": None,
    }
    return VolumeChange(**(values | fields))


@pytest.mark.anyio
async def test_a_volume_change_sets_its_fields_locked_its_image_and_reads_it_again() -> None:
    jellyfin = shelf()
    jellyfin.items["b2"]["People"] = [
        {"Name": "Old", "Type": "Author"},
        {"Name": "X", "Type": "Translator"},
    ]
    service, _ = service_of(jellyfin)

    changed = await service.change_volume(
        "b2", volume_change(number=3, image=LinkImage(url="https://x.test/c.jpg"))
    )

    volume = jellyfin.items["b2"]
    assert (volume["Name"], volume["IndexNumber"], volume["Overview"]) == (
        "Berserk - T02 - Le Guerrier noir",
        3,
        "Guts.",
    )
    assert volume["People"] == [
        {"Name": "Kentaro Miura", "Type": "Author", "Role": ""},
        {"Name": "Studio Gaga", "Type": "Author", "Role": ""},
        {"Name": "X", "Type": "Translator"},
    ]
    assert volume["LockedFields"] == ["Cast", "Name", "Overview"]
    # Read back whole: the rest of the item stays.
    assert volume["Path"] == "/files/comics/Berserk/Berserk - T02.cbz"
    assert jellyfin.images["b2"] == JPEG
    assert (changed.id, changed.number, changed.size) == ("b2", 3, 10)
    assert jellyfin.refreshed == [("b2", AFTER_CHANGE)]
    unlocked = await service.change_volume("b1", volume_change(lock=False))
    assert "LockedFields" not in jellyfin.items["b1"] or not jellyfin.items["b1"]["LockedFields"]
    assert unlocked.name == "Berserk - T02 - Le Guerrier noir"


@pytest.mark.anyio
async def test_a_volume_change_refuses_a_folder_and_an_image_that_is_not_one() -> None:
    jellyfin = shelf()
    service, _ = service_of(jellyfin)

    with pytest.raises(VolumeNotFoundError):
        await service.change_volume("berserk", volume_change())
    with pytest.raises(ImageRefusedError):
        await service.change_volume("b2", volume_change(image=SentImage(data=b"<svg/>")))
    assert jellyfin.items["b2"]["Name"] == "Berserk - T02.cbz"
