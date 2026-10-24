"""The messages of the journal: the events of one batch made into one Discord embed. Pure: no
I/O."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Final

from shelfdrop.journal.texts import CLIENTS, DEFAULT_CLIENT, FOOTER
from shelfdrop.journal.types import COLORS, Event, Fact, JournalTexts

# Discord refuses a field value over 1024 characters, a description over 4096.
FIELD_MAX: Final = 1024
DESCRIPTION_MAX: Final = 4000


def volumes_label(numbers: Sequence[int], texts: JournalTexts) -> str:
    """'T01 à T22'; 'T01, T03 et T05 à T07' ('Vol. 01, Vol. 03 and Vol. 05 to 07'):
    consecutive volumes as ranges."""
    ordered = sorted(set(numbers))
    runs: list[tuple[int, int]] = []
    for n in ordered:
        if runs and n == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    parts = [texts.volume.format(a) if a == b else texts.volume_range.format(a, b) for a, b in runs]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + texts.last_join + parts[-1]


def size_label(size: int, texts: JournalTexts) -> str:
    """'850 Mo', '1,2 Go'; '850 MB', '1.2 GB' (decimal units)."""
    if size >= 10**9:
        return texts.gigabytes.format(f"{size / 10**9:.1f}".replace(".", texts.decimal))
    return texts.megabytes.format(max(1, round(size / 10**6)))


def duration_label(seconds: int, texts: JournalTexts) -> str:
    """'45 s', '12 min', '2 h 05'; '2 h 5 min'."""
    if seconds < 60:
        return texts.seconds.format(seconds)
    minutes = seconds // 60
    if minutes < 60:
        return texts.minutes.format(minutes)
    return texts.hours.format(hours=minutes // 60, minutes=minutes % 60)


def chapter_label(value: Fact) -> str:
    number = value if isinstance(value, int | float) and not isinstance(value, bool) else 0
    return str(int(number)) if number == int(number) else str(number)


def target_label(facts: Mapping[str, Fact], texts: JournalTexts) -> str:
    """What a waiting search found: 'T03', 'Ch. 233 et suivants', 'Toute release'. An event
    recorded before its facts `wanted` gives its label `target`, in French."""
    match facts.get("wanted"):
        case "any":
            return texts.any_release
        case "volume":
            return texts.volume.format(number(facts.get("volume")))
        case "chapters":
            start = chapter_label(facts.get("chapter_from"))
            if facts.get("chapter_to") is None:
                return texts.chapters_from.format(start)
            return texts.chapters_range.format(start, chapter_label(facts.get("chapter_to")))
        case _:
            return text(facts.get("target"))


def text(value: Fact) -> str:
    return "" if value is None else str(value)


def numbers(value: Fact) -> list[int]:
    return [n for n in value if isinstance(n, int)] if isinstance(value, list) else []


def number(value: Fact) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def unique(values: Sequence[str]) -> list[str]:
    return [v for v in dict.fromkeys(values) if v]


def lines(values: Sequence[str]) -> str:
    return "\n".join(unique(values))[:DESCRIPTION_MAX]


def client_name(value: Fact) -> str:
    """The name of the torrent client of a fact `client`; qBittorrent without one."""
    return CLIENTS.get(text(value), DEFAULT_CLIENT)


def field(name: str, value: str, *, inline: bool = True) -> dict[str, Any]:
    return {"name": name, "value": value[:FIELD_MAX], "inline": inline}


def fields_of(
    events: Sequence[Event], texts: JournalTexts
) -> tuple[str, str, list[dict[str, Any]]]:
    """The subject of the title, the description and the fields of the events of one type."""
    first = events[0]
    facts = [e.facts for e in events]
    match first.type:
        case "sent":
            found = [n for f in facts for n in numbers(f.get("volumes"))]
            fields = [] if not found else [field(texts.volumes, volumes_label(found, texts))]
            fields += [
                field(texts.trackers, ", ".join(unique([text(f.get("tracker")) for f in facts]))),
                field(texts.size, size_label(sum(number(f.get("size")) for f in facts), texts)),
                field(texts.mode, texts.modes.get(text(first.facts.get("mode")), "")),
                field(texts.by, text(first.facts.get("actor"))),
            ]
            return text(first.facts.get("work")), "", fields
        case "downloaded":
            fields = [
                field(texts.size, size_label(sum(number(f.get("size")) for f in facts), texts))
            ]
            seconds = max(number(f.get("seconds")) for f in facts)
            if seconds:
                fields.append(field(texts.duration, duration_label(seconds, texts)))
            return (
                text(first.facts.get("work")),
                lines([text(f.get("release")) for f in facts]),
                fields,
            )
        case "placed":
            placed = [n for f in facts for n in numbers(f.get("volumes"))]
            skipped = [n for f in facts for n in numbers(f.get("skipped"))]
            fields = [] if not placed else [field(texts.volumes, volumes_label(placed, texts))]
            if skipped:
                fields.append(field(texts.already, volumes_label(skipped, texts)))
            return text(first.facts.get("destination")), "", fields
        case "to_place":
            reasons = unique([texts.reasons.get(text(f.get("reason")), "") for f in facts])
            fields = [field(texts.reason, ", ".join(reasons))]
            body = lines([text(f.get("release")) for f in facts]) + "\n" + texts.place
            return text(first.facts.get("work")), body.strip(), fields
        case "retry":
            fields = [
                field(texts.attempt, str(max(number(f.get("attempt")) for f in facts))),
                field(
                    texts.result,
                    ", ".join(
                        unique(
                            [
                                texts.results.get(text(f.get("result")), "").format(
                                    client=client_name(f.get("client"))
                                )
                                for f in facts
                            ]
                        )
                    ),
                ),
            ]
            return (
                text(first.facts.get("work")),
                lines([text(f.get("release")) for f in facts]),
                fields,
            )
        case "failed":
            what = text(first.facts.get("what"))
            fields = [field(texts.done, texts.actions.get(what, ""), inline=False)]
            errors = unique([text(f.get("error")) for f in facts])
            if errors:
                fields.insert(0, field(texts.error, ", ".join(errors)))
            body = lines([text(f.get("release")) for f in facts])
            title = texts.failures.get(what, what)
            if what in texts.failures:
                title = title.format(client=client_name(first.facts.get("client")))
            return title, body, fields
        case "login":
            # Never the address itself on Discord: its country alone.
            fields = []
            country = text(first.facts.get("country"))
            if country:
                fields.append(field(texts.country, country))
            if first.facts.get("refused") is True:
                return texts.refused, "", fields
            return text(first.facts.get("account")), "", fields
        case "found":
            fields = [
                field(texts.releases, str(max(number(f.get("releases")) for f in facts))),
            ]
            return (
                text(first.facts.get("work")),
                lines([target_label(f, texts) for f in facts]),
                fields,
            )
        case "uploaded":
            fields = [
                field(texts.size, size_label(sum(number(f.get("size")) for f in facts), texts))
            ]
            types = unique([text(f.get("type")) for f in facts])
            if types:
                fields.append(field(texts.type, ", ".join(types)))
            return "", lines([text(f.get("file")) for f in facts]), fields
        case "misplaced":
            counts: dict[str, int] = {}
            for f in facts:
                library = text(f.get("library"))
                counts[library] = counts.get(library, 0) + int(number(f.get("count")))
            fields = [field(library, str(count)) for library, count in counts.items()]
            return "", texts.place, fields


def embed_of(
    events: Sequence[Event], public_url: str | None, cover: str | None, texts: JournalTexts
) -> dict[str, Any]:
    """One embed for the events of one batch (same type, same group), `cover` the name of the
    picture joined to the message, in the language of `texts`."""
    first = events[0]
    subject, description, fields = fields_of(events, texts)
    name = texts.titles[first.type]
    title = name if not subject else f"{name}{texts.separator}{subject}"
    embed: dict[str, Any] = {
        "title": title[:256],
        "color": COLORS[first.type],
        "footer": {"text": FOOTER},
        "timestamp": datetime.fromtimestamp(max(e.created_at for e in events), UTC).isoformat(),
        "fields": [f for f in fields if f["value"]],
    }
    if description:
        embed["description"] = description
    if public_url:
        embed["url"] = public_url
    if cover is not None:
        embed["thumbnail"] = {"url": f"attachment://{cover}"}
    return embed
