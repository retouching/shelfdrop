"""The work searches every fixture is recorded from, with what each must find.

Recorded on 2026-10-21, without a MyAnimeList Client ID, when AniList was down: its exchanges
are replayed as failures, which also covers the case of a source that does not answer.
"""

from dataclasses import dataclass, field

from shelfdrop.works.types import Kind


@dataclass(frozen=True)
class Case:
    slug: str
    query: str
    kind: Kind
    shelf_name: str
    """Expected name in the library for the first work."""
    names: tuple[str, ...] = ()
    """Names that must be checked (searched on Prowlarr) for the first work."""
    author: str | None = None
    volumes: int | None = None
    volumes_fr: int | None = None
    not_first: tuple[str, ...] = field(default=())
    """Shelf names that must not come first."""
    unchecked: tuple[str, ...] = ()
    """Names of the first work in a language not searched by default, or in none known: they
    are shown, unchecked."""


CASES = (
    Case(
        "chainsaw-man",
        "Chainsaw Man",
        "manga",
        "Chainsaw Man",
        names=("Chainsaw Man", "Chensoo Man"),
        author="Tatsuki Fujimoto",
        volumes=24,
        unchecked=("Testere Adam", "Omul Drujbă", "Chainsaw Man: Public Safety Saga"),
    ),
    Case(
        "atelier-des-sorciers",
        "L'atelier des sorciers",
        "manga",
        "L'atelier des sorciers",
        names=("Tongari Boushi no Atelier", "Witch Hat Atelier"),
        author="Kamome Shirahama",
        unchecked=(
            "Asrama Topi Lancip",
            "Pondok Penyihir Topi Lancip",
            "Atelier of Witch Hat (Indonesian)",
            "Ateliér špičatých klobouků",
            "Atelier spiczastych kapeluszy",
            "El Atelier del Sombrero Puntiagudo",
        ),
    ),
    Case(
        "dusk-maiden",
        "Dusk Maiden of Amnesia",
        "manga",
        "Dusk Maiden of Amnesia",
        names=("Dusk Maiden of Amnesia",),
        volumes=10,
        volumes_fr=10,
        not_first=("Amnesia",),
        unchecked=("Niepamięć Panny Zmierzchu (Polish)", "Koukin Otome x Amnesia"),
    ),
    Case(
        "kaguya-sama",
        "Kaguya-sama",
        "manga",
        "Kaguya-sama: Love is War",
        names=("Kaguya-sama: Love is War",),
        volumes=28,
        unchecked=("Kaguya Ingin Dicintai: Perang Cerdik dalam Cinta dan Akal",),
    ),
    Case(
        "berserk",
        "Berserk",
        "manga",
        "Berserk",
        names=("Berserk",),
        author="Kentaro Miura",
    ),
    Case(
        "can-t-hurt-me",
        "Can't Hurt Me",
        "ebook",
        "Plus rien ne pourra me blesser",
        names=("Plus rien ne pourra me blesser", "Can't Hurt Me"),
        author="David Goggins",
    ),
    Case(
        "plus-rien",
        "plus rien ne pourra me blesser",
        "ebook",
        "Plus rien ne pourra me blesser",
        author="David Goggins",
    ),
    Case(
        "bone-season",
        "The Bone Season",
        "ebook",
        "The Bone Season",
        names=("The Bone Season", "Saison d'os"),
        author="Samantha Shannon",
    ),
    Case(
        "memoire-des-os",
        "La Mémoire des os",
        "audiobook",
        "La mémoire des os",
    ),
)
