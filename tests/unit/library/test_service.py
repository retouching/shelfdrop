"""LibraryService: the series of the libraries of Jellyfin, their proposals, their changes, the
summaries by batch and the scans, on the fake Jellyfin."""

from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from shelfdrop.clients.jellyfin import JellyfinClient
from shelfdrop.library.exceptions import ImageRefusedError, SeriesNotFoundError
from shelfdrop.library.service import LibraryService, series_folder
from shelfdrop.library.types import ItemImage, LinkImage, ScanOrder, SentImage, SeriesChange
from shelfdrop.works.exceptions import NoSourceAnsweredError
from shelfdrop.works.types import Kind, Work, WorkSearch
from tests.unit.clients.support import API_KEY, FakeJellyfin
from tests.unit.placement.support import FakePlacementRepository, libraries_of
from tests.unit.works.support import FixedClock

JPEG = b"\xff\xd8\xff\xe0image"
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

    assert [(v.item_id, v.label) for v in proposals.volumes] == [("b1", "Tome 1 \u00b7 CBZ")]
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
