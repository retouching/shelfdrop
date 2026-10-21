"""The messages of the journal: the events of one batch made into one Discord embed. Pure: no
I/O."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final

from shelfdrop.journal import texts
from shelfdrop.journal.types import COLORS, Event, Fact

# Discord refuses a field value over 1024 characters, a description over 4096.
FIELD_MAX: Final = 1024
DESCRIPTION_MAX: Final = 4000


def volume(number: int) -> str:
    return f"T{number:02d}"


def volumes_label(numbers: Sequence[int]) -> str:
    """'T01 à T22'; 'T01, T03 et T05 à T07': consecutive volumes as ranges."""
    ordered = sorted(set(numbers))
    runs: list[tuple[int, int]] = []
    for n in ordered:
        if runs and n == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    parts = [volume(a) if a == b else f"{volume(a)} à {volume(b)}" for a, b in runs]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " et " + parts[-1]


def size_label(size: int) -> str:
    """'850 Mo', '1,2 Go' (decimal units, French decimal comma)."""
    if size >= 10**9:
        return f"{size / 10**9:.1f} Go".replace(".", ",")
    return f"{max(1, round(size / 10**6))} Mo"


def duration_label(seconds: int) -> str:
    """'45 s', '12 min', '2 h 05'."""
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d}"


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


def field(name: str, value: str, *, inline: bool = True) -> dict[str, Any]:
    return {"name": name, "value": value[:FIELD_MAX], "inline": inline}


def fields_of(events: Sequence[Event]) -> tuple[str, str, list[dict[str, Any]]]:
    """The subject of the title, the description and the fields of the events of one type."""
    first = events[0]
    facts = [e.facts for e in events]
    match first.type:
        case "sent":
            found = [n for f in facts for n in numbers(f.get("volumes"))]
            fields = [] if not found else [field(texts.VOLUMES, volumes_label(found))]
            fields += [
                field(texts.TRACKERS, ", ".join(unique([text(f.get("tracker")) for f in facts]))),
                field(texts.SIZE, size_label(sum(number(f.get("size")) for f in facts))),
                field(texts.MODE, texts.MODES.get(text(first.facts.get("mode")), "")),
                field(texts.BY, text(first.facts.get("actor"))),
            ]
            return text(first.facts.get("work")), "", fields
        case "downloaded":
            fields = [field(texts.SIZE, size_label(sum(number(f.get("size")) for f in facts)))]
            seconds = max(number(f.get("seconds")) for f in facts)
            if seconds:
                fields.append(field(texts.DURATION, duration_label(seconds)))
            return (
                text(first.facts.get("work")),
                lines([text(f.get("release")) for f in facts]),
                fields,
            )
        case "placed":
            placed = [n for f in facts for n in numbers(f.get("volumes"))]
            skipped = [n for f in facts for n in numbers(f.get("skipped"))]
            fields = [] if not placed else [field(texts.VOLUMES, volumes_label(placed))]
            if skipped:
                fields.append(field(texts.ALREADY, volumes_label(skipped)))
            return text(first.facts.get("destination")), "", fields
        case "to_place":
            reasons = unique([texts.REASONS.get(text(f.get("reason")), "") for f in facts])
            fields = [field(texts.REASON, ", ".join(reasons))]
            body = lines([text(f.get("release")) for f in facts]) + "\n" + texts.PLACE
            return text(first.facts.get("work")), body.strip(), fields
        case "retry":
            fields = [
                field(texts.ATTEMPT, str(max(number(f.get("attempt")) for f in facts))),
                field(
                    texts.RESULT,
                    ", ".join(
                        unique([texts.RESULTS.get(text(f.get("result")), "") for f in facts])
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
            fields = [field(texts.DONE, texts.ACTIONS.get(what, ""), inline=False)]
            errors = unique([text(f.get("error")) for f in facts])
            if errors:
                fields.insert(0, field(texts.ERROR, ", ".join(errors)))
            body = lines([text(f.get("release")) for f in facts])
            return texts.FAILURES.get(what, what), body, fields
        case "login":
            fields = [field(texts.ADDRESS, text(first.facts.get("address")))]
            country = text(first.facts.get("country"))
            if country:
                fields.append(field(texts.COUNTRY, country))
            if first.facts.get("refused") is True:
                return texts.REFUSED, "", fields
            return text(first.facts.get("account")), "", fields
        case "found":
            fields = [
                field(texts.RELEASES, str(max(number(f.get("releases")) for f in facts))),
            ]
            return (
                text(first.facts.get("work")),
                lines([text(f.get("target")) for f in facts]),
                fields,
            )
        case "uploaded":
            fields = [field(texts.SIZE, size_label(sum(number(f.get("size")) for f in facts)))]
            types = unique([text(f.get("type")) for f in facts])
            if types:
                fields.append(field(texts.TYPE, ", ".join(types)))
            return "", lines([text(f.get("file")) for f in facts]), fields
        case "misplaced":
            counts: dict[str, int] = {}
            for f in facts:
                library = text(f.get("library"))
                counts[library] = counts.get(library, 0) + int(number(f.get("count")))
            fields = [field(library, str(count)) for library, count in counts.items()]
            return "", texts.PLACE, fields


def embed_of(events: Sequence[Event], public_url: str | None, cover: str | None) -> dict[str, Any]:
    """One embed for the events of one batch (same type, same group), `cover` the name of the
    picture joined to the message."""
    first = events[0]
    subject, description, fields = fields_of(events)
    title = texts.TITLES[first.type] if not subject else f"{texts.TITLES[first.type]} : {subject}"
    embed: dict[str, Any] = {
        "title": title[:256],
        "color": COLORS[first.type],
        "footer": {"text": texts.FOOTER},
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
