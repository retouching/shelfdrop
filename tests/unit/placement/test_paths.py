"""shelfdrop.placement.paths: the libraries as Jellyfin sees them and as the placement sees
them."""

import pytest

from shelfdrop.clients.types import JellyfinLibrary
from shelfdrop.placement.paths import destination_label, library_of, to_jellyfin, to_local
from shelfdrop.works.types import Kind

LIBRARIES = [
    JellyfinLibrary(name="Films", collection_type="movies", locations=("/films",)),
    JellyfinLibrary(
        name="BD & Mangas", collection_type="books", item_id="l1", locations=("/files/comics",)
    ),
]
ROOTS: dict[Kind, str] = {"manga": "/data/files/comics", "ebook": "/data/files/ebooks"}


def test_a_library_is_the_one_whose_folder_has_the_name_of_the_folder_of_its_kind() -> None:
    library, location = library_of("/data/files/comics", LIBRARIES)

    assert (library.item_id, location) == ("l1", "/files/comics")
    with pytest.raises(LookupError):
        library_of("/data/files/ebooks", LIBRARIES)


def test_a_path_goes_both_ways_and_never_out_of_a_library() -> None:
    local = "/data/files/comics/Berserk/Berserk - T41.cbz"

    seen = to_jellyfin(local, "/data/files/comics", "/files/comics")

    assert seen == "/files/comics/Berserk/Berserk - T41.cbz"
    assert to_local(seen, ROOTS, LIBRARIES) == local
    with pytest.raises(LookupError):
        to_local("/files/comics/../../etc", ROOTS, LIBRARIES)
    with pytest.raises(LookupError):
        to_local("/films/x.mkv", ROOTS, LIBRARIES)


def test_the_destination_names_the_library_then_the_series() -> None:
    assert destination_label("manga", "Berserk", LIBRARIES[1]) == "BD & Mangas \u203a Berserk"
    assert destination_label("audiobook", "Ne cède jamais", None) == (
        "Livres audio \u203a Ne cède jamais"
    )
