"""The catalog of the settings of the page: their keys, kinds, defaults and bounds, and the
keys of the secrets. Pure: no I/O."""

import re
from collections.abc import Mapping
from typing import Final

from shelfdrop.settings.types import Entry, SettingValue
from shelfdrop.works.types import Kind, SourceName

# The services shelfdrop calls: an address and a secret each (the torrent client: the secret of
# its client, `torrent_secret`).
SERVICES: Final = ("prowlarr", "torrent", "jellyfin")
# The torrent clients the setting `torrent.client` takes; a client no connector serves yet is
# refused by the test of the connection (shelfdrop.clients.torrents.factory.CONNECTORS).
CLIENTS: Final = ("qui", "qbittorrent", "deluge", "transmission")
# The downloads that may have a folder of their own in the torrent client: by kind, and manual.
TORRENT_FOLDERS: Final = ("manga", "ebook", "audiobook", "manual")
# The name a secret was sealed under before a revision moved it: it opens under it until it is
# saved again (shelfdrop/db/migrations/versions/, the move of `qbittorrent.*` to `torrent.*`).
FORMER_NAMES: Final[Mapping[str, str]] = {"torrent.api_key": "qbittorrent.api_key"}
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
# The languages of the messages of the journal.
LANGUAGES: Final = ("fr", "en")
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
TEXT_MAX_LENGTH: Final = 255

VALUES: Final[Mapping[str, Entry]] = {
    **{f"{service}.url": Entry(kind="address", default=None) for service in SERVICES},
    **{f"sources.{source}.enabled": Entry(kind="switch", default=True) for source in SOURCES},
    "search.max_names": Entry(kind="number", default=6, minimum=1, maximum=10),
    "search.release_cache_minutes": Entry(kind="number", default=10, minimum=0, maximum=1440),
    "search.work_cache_hours": Entry(kind="number", default=24, minimum=0, maximum=720),
    **{f"discord.events.{event}": Entry(kind="switch", default=True) for event in EVENTS},
    "journal.language": Entry(kind="choice", default="fr", options=LANGUAGES),
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
    # The torrent client and how it signs in (its address: `torrent.url`, its secrets:
    # `torrent.password`, `torrent.api_key`, the key of the client proxy of qui).
    "torrent.client": Entry(kind="choice", default="qui", options=CLIENTS),
    "torrent.username": Entry(kind="text", default=None),
    # The folder of the client the downloads of a kind go to, as the client sees it; unset, the
    # client chooses (qBittorrent: the folder of the category).
    **{f"torrent.folder.{name}": Entry(kind="path", default=None) for name in TORRENT_FOLDERS},
}
SECRETS: Final = frozenset(
    {
        *(f"{service}.api_key" for service in SERVICES),
        "torrent.password",
        "sources.myanimelist.client_id",
        "discord.webhook",
    }
)


def torrent_secret(client: str) -> str:
    """The key of the secret `client` signs in with: the key of the proxy of qui, the password
    of the others."""
    return "torrent.api_key" if client == "qui" else "torrent.password"


def sealed_names(key: str) -> tuple[str, ...]:
    """The names a secret saved under `key` may be sealed under: its own, then its former one."""
    former = FORMER_NAMES.get(key)
    return (key,) if former is None else (key, former)


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
            if value is None:
                return entry.default is None
            return isinstance(value, str) and is_path(value)
        case "time":
            return isinstance(value, str) and TIME.match(value) is not None
        case "choice":
            return isinstance(value, str) and value in (entry.options or ())
        case "text":
            return value is None or (
                isinstance(value, str)
                and 0 < len(value) <= TEXT_MAX_LENGTH
                and value.isprintable()
                and value == value.strip()
            )


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
