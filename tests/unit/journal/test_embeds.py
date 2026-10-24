"""shelfdrop.journal.embeds: the events of one batch made into one embed (plan section 3,
point 7)."""

import pytest

from shelfdrop.journal.embeds import duration_label, embed_of, size_label, volumes_label
from shelfdrop.journal.types import Event, EventType, Fact


def event(event_type: EventType, **facts: Fact) -> Event:
    return Event(
        id=1,
        type=event_type,
        group="g",
        facts=facts,
        cover=None,
        created_at=1792620000,
        attempts=0,
    )


@pytest.mark.parametrize(
    ("numbers", "label"),
    [
        (list(range(1, 23)), "T01 à T22"),
        ([1, 3, 5, 6, 7], "T01, T03 et T05 à T07"),
        ([4], "T04"),
        ([2, 1, 2], "T01 à T02"),
    ],
)
def test_the_volumes_are_written_as_ranges(numbers: list[int], label: str) -> None:
    assert volumes_label(numbers) == label


def test_sizes_and_durations_are_written_in_french() -> None:
    assert size_label(850_000_000) == "850 Mo"
    assert size_label(1_234_000_000) == "1,2 Go"
    assert duration_label(45) == "45 s"
    assert duration_label(720) == "12 min"
    assert duration_label(7500) == "2 h 05"


def test_twenty_two_volumes_sent_make_one_embed() -> None:
    events = [
        event(
            "sent",
            work="Chainsaw Man",
            volumes=[n],
            tracker="Nyaa.si" if n % 2 else "ABN",
            size=100_000_000,
            mode="auto",
            actor="sylvain",
        )
        for n in range(1, 23)
    ]

    embed = embed_of(events, "https://shelfdrop.maigo.party", None)

    assert embed["title"] == "Envoyé : Chainsaw Man"
    assert embed["color"] == 0x6E56CF
    assert embed["url"] == "https://shelfdrop.maigo.party"
    assert embed["footer"] == {"text": "shelfdrop"}
    assert embed["timestamp"].startswith("2026-")
    assert {f["name"]: f["value"] for f in embed["fields"]} == {
        "Tomes": "T01 à T22",
        "Trackers": "Nyaa.si, ABN",
        "Taille": "2,2 Go",
        "Mode": "Automatique",
        "Par": "sylvain",
    }
    assert "thumbnail" not in embed


def test_a_placement_shows_its_destination_its_volumes_and_the_cover_joined() -> None:
    placed = event("placed", destination="BD & Mangas › Berserk", volumes=[41, 42], skipped=[40])

    embed = embed_of([placed], None, "cover.jpg")

    assert embed["title"] == "Rangé : BD & Mangas › Berserk"
    assert embed["color"] == 0x30A46C
    assert embed["thumbnail"] == {"url": "attachment://cover.jpg"}
    assert [(f["name"], f["value"]) for f in embed["fields"]] == [
        ("Tomes", "T41 à T42"),
        ("Déjà présents", "T40"),
    ]
    assert "url" not in embed


def test_a_refused_sign_in_names_the_country_alone_never_the_address() -> None:
    refused = event("login", refused=True, address="203.0.113.9", country="DE")

    embed = embed_of([refused], None, None)

    assert embed["title"] == "Connexion : Connexions refusées depuis la même adresse"
    assert [(f["name"], f["value"]) for f in embed["fields"]] == [("Pays", "DE")]
    assert "203.0.113.9" not in str(embed)


def test_a_failure_says_what_shelfdrop_did() -> None:
    failed = event("failed", what="not_received", release="Berserk.T01.CBZ")

    embed = embed_of([failed], None, None)

    assert embed["title"] == "Échec : qBittorrent n'a pas reçu le torrent"
    assert embed["description"] == "Berserk.T01.CBZ"
    assert embed["fields"][-1]["value"] == "Rien d'envoyé. Réessayer depuis Téléchargements."


def test_the_files_misplaced_are_counted_by_library() -> None:
    embed = embed_of(
        [
            event("misplaced", library="BD & Mangas", count=2),
            event("misplaced", library="Livres", count=1),
            event("misplaced", library="BD & Mangas", count=1),
        ],
        None,
        None,
    )

    assert embed["title"] == "Mal rangés"
    assert embed["description"] == "À ranger dans Ranger."
    assert [(f["name"], f["value"]) for f in embed["fields"]] == [
        ("BD & Mangas", "3"),
        ("Livres", "1"),
    ]


def test_a_file_sent_gives_its_name_its_size_and_its_type() -> None:
    embed = embed_of(
        [event("uploaded", file="Berserk T41.cbz", size=850_000_000, type="CBZ")], None, None
    )

    assert embed["title"] == "Fichier envoyé"
    assert embed["description"] == "Berserk T41.cbz"
    assert embed["fields"] == [
        {"name": "Taille", "value": "850 Mo", "inline": True},
        {"name": "Type", "value": "CBZ", "inline": True},
    ]


def test_a_corrupt_file_sent_is_a_failure_that_says_what_was_done() -> None:
    embed = embed_of(
        [event("failed", what="upload_corrupt", release="Berserk T41.cbz", error="SHA-256")],
        None,
        None,
    )

    assert embed["title"] == "Échec : Envoi corrompu"
    assert {
        "name": "Ce que shelfdrop a fait",
        "value": "Fichier supprimé, à envoyer de nouveau.",
        "inline": False,
    } in (embed["fields"])
