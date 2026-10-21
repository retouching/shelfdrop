"""The catalog of the settings of the page: their keys, kinds, defaults and bounds, and the
keys of the secrets. Pure: no I/O."""

import re
from collections.abc import Mapping
from typing import Final

from shelfdrop.settings.types import Entry, SettingValue
from shelfdrop.works.types import SourceName

# The services shelfdrop calls: an address and an API key each.
SERVICES: Final = ("prowlarr", "qbittorrent", "jellyfin")
# The metadata sources, in the order of the page.
SOURCES: Final[tuple[SourceName, ...]] = (
    "mangaupdates",
    "kitsu",
    "myanimelist",
    "anilist",
    "mangadex",
    "bnf",
    "openlibrary",
    "wikidata",
)
# The events of the journal sent to Discord (plan section 3, point 7).
EVENTS: Final = (
    "sent",
    "downloaded",
    "placed",
    "to_place",
    "uploaded",
    "retry",
    "failed",
    "misplaced",
    "login",
)
ADDRESS: Final = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d+)?(/\S*)?$")
SECRET_MAX_LENGTH: Final = 1000

VALUES: Final[Mapping[str, Entry]] = {
    **{f"{service}.url": Entry(kind="address", default=None) for service in SERVICES},
    **{f"sources.{source}.enabled": Entry(kind="switch", default=True) for source in SOURCES},
    "search.max_names": Entry(kind="number", default=6, minimum=1, maximum=10),
    "search.release_cache_minutes": Entry(kind="number", default=10, minimum=0, maximum=1440),
    "search.work_cache_hours": Entry(kind="number", default=24, minimum=0, maximum=720),
    **{f"discord.events.{event}": Entry(kind="switch", default=True) for event in EVENTS},
}
SECRETS: Final = frozenset(
    {
        *(f"{service}.api_key" for service in SERVICES),
        "sources.myanimelist.client_id",
        "discord.webhook",
    }
)


def is_valid(entry: Entry, value: SettingValue) -> bool:
    match entry.kind:
        case "address":
            return value is None or (isinstance(value, str) and ADDRESS.match(value) is not None)
        case "switch":
            return isinstance(value, bool)
        case "number":
            return (
                isinstance(value, int)
                and not isinstance(value, bool)
                and (entry.minimum is None or value >= entry.minimum)
                and (entry.maximum is None or value <= entry.maximum)
            )


def invalid_keys(
    values: Mapping[str, SettingValue], secrets: Mapping[str, str | None]
) -> list[str]:
    """The keys the catalog does not know, or whose value it refuses: a secret is 1 to 1000
    printable characters, without spaces."""
    refused = [
        key
        for key, value in values.items()
        if key not in VALUES or not is_valid(VALUES[key], value)
    ]
    refused += [
        key
        for key, secret in secrets.items()
        if key not in SECRETS
        or (
            secret is not None
            and not (
                0 < len(secret) <= SECRET_MAX_LENGTH and secret.isprintable() and " " not in secret
            )
        )
    ]
    return sorted(refused)
