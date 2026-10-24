"""The catalog of the settings of the page: their keys, kinds, defaults and bounds, and the
keys of the secrets. Pure: no I/O."""

import re
from collections.abc import Mapping
from typing import Final

from shelfdrop.settings.types import Entry, SettingValue
from shelfdrop.works.types import Kind, SourceName

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
# The events of the journal sent to Discord.
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
    "found",
)
# The libraries of each kind, as the container sees them (one mount of the media folder on
# /data, the torrents and the libraries on one file system).
LIBRARIES: Final[dict[Kind, str]] = {
    "manga": "/data/files/comics",
    "ebook": "/data/files/ebooks",
    "audiobook": "/data/files/audiobooks",
}
PATH_MAX_LENGTH: Final = 500
# Hours between two searches of the waiting list.
WAITING_HOURS: Final = (1, 3, 6, 12, 24)
# A time of the day, `04:30`.
TIME: Final = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
ADDRESS: Final = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d+)?(/\S*)?$")
SECRET_MAX_LENGTH: Final = 1000

VALUES: Final[Mapping[str, Entry]] = {
    **{f"{service}.url": Entry(kind="address", default=None) for service in SERVICES},
    **{f"sources.{source}.enabled": Entry(kind="switch", default=True) for source in SOURCES},
    "search.max_names": Entry(kind="number", default=6, minimum=1, maximum=10),
    "search.release_cache_minutes": Entry(kind="number", default=10, minimum=0, maximum=1440),
    "search.work_cache_hours": Entry(kind="number", default=24, minimum=0, maximum=720),
    **{f"discord.events.{event}": Entry(kind="switch", default=True) for event in EVENTS},
    **{
        f"placement.library.{kind}": Entry(kind="path", default=path)
        for kind, path in LIBRARIES.items()
    },
    "placement.merge_mp3": Entry(kind="switch", default=True),
    "waiting.interval_hours": Entry(kind="number", default=6, choices=WAITING_HOURS),
    "placement.covers": Entry(kind="switch", default=True),
    "placement.lock_jellyfin": Entry(kind="switch", default=True),
    # The time of the day of the scan of the files misplaced.
    "placement.scan_time": Entry(kind="time", default="04:30"),
    # The folder the files sent from the page wait in, as the placement worker sees it: on the
    # file system of the libraries.
    "uploads.folder": Entry(kind="path", default="/data/envois"),
    "uploads.keep_days": Entry(kind="number", default=7, minimum=1, maximum=365),
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
                and (entry.choices is None or value in entry.choices)
            )
        case "path":
            return isinstance(value, str) and is_path(value)
        case "time":
            return isinstance(value, str) and TIME.match(value) is not None


def is_path(value: str) -> bool:
    """An absolute path of the container: printable, without `..` nor a trailing slash."""
    parts = value.split("/")
    return (
        0 < len(value) <= PATH_MAX_LENGTH
        and value.startswith("/")
        and value.isprintable()
        and ".." not in parts
        and (value == "/" or not value.endswith("/"))
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
