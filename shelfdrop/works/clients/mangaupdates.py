"""MangaUpdates (api.mangaupdates.com/v1): manga, with every associated name, in any language.

The search matches associated names too, French ones included ("L'atelier des sorciers" finds
"Tongari Boushi no Atelier"). Names and authors come from the series page, fetched for the best
few hits only.
"""

import contextlib
import re
from typing import Any

import anyio
import httpx

from shelfdrop.utils.text import is_latin, plain, script_of
from shelfdrop.works.clients.http import get_json, post_json, year_of
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.names import person_name
from shelfdrop.works.types import Candidate, Family, Form, Name, SourceName

API = "https://api.mangaupdates.com/v1"
DETAILS = 4

FORMS: dict[str, Form] = {
    "manga": "manga",
    "manhwa": "manga",
    "manhua": "manga",
    "oel": "manga",
    "novel": "novel",
    "doujinshi": "doujinshi",
    "artbook": "other",
}
VOLUMES = re.compile(r"(\d+)\s+Volumes?", re.IGNORECASE)


def form_of(record: dict[str, Any]) -> Form:
    form = FORMS.get(str(record.get("type", "")).lower(), "other")
    title = str(record.get("title", "")).lower()
    if form == "manga" and ("anthology" in title or "dj - " in title):
        return "anthology" if "anthology" in title else "doujinshi"
    return form


def volumes_of(status: str) -> int | None:
    found = VOLUMES.search(status or "")
    return int(found.group(1)) if found else None


def name_of(title: str) -> Name:
    # MangaUpdates does not say which language a name is in; the script tells some of it.
    return Name(title=title, language="latin" if is_latin(title) else script_of(title))


class MangaUpdatesClient:
    name: SourceName = "mangaupdates"
    families: frozenset[Family] = frozenset({"manga"})

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def search(self, query: str, family: Family) -> list[Candidate]:
        body = await post_json(self.http, f"{API}/series/search", {"search": query, "perpage": 10})
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise SourceError("unexpected body")
        records = [r["record"] for r in body["results"] if isinstance(r, dict) and "record" in r]
        details: dict[int, dict[str, Any]] = {}

        async def detail(series_id: int) -> None:
            # on failure, the search hit alone still makes a candidate
            with contextlib.suppress(SourceError):
                details[series_id] = await get_json(self.http, f"{API}/series/{series_id}")

        async with anyio.create_task_group() as group:
            for record in records[:DETAILS]:
                group.start_soon(detail, int(record["series_id"]))
        return [self.candidate_of(r, details.get(int(r["series_id"]))) for r in records]

    def candidate_of(self, record: dict[str, Any], detail: dict[str, Any] | None) -> Candidate:
        full = detail or record
        names = [name_of(record["title"])]
        names += [name_of(a["title"]) for a in full.get("associated", []) if a.get("title")]
        authors: list[str] = []
        for author in full.get("authors", []):
            name = person_name(str(author.get("name", "")))
            if name and name not in authors:
                authors.append(name)
        image = (record.get("image") or {}).get("url") or {}
        rating = float(record.get("bayesian_rating") or 0)
        return Candidate(
            source="mangaupdates",
            source_id=str(record["series_id"]),
            title=record["title"],
            names=tuple(names),
            authors=tuple(authors),
            year=year_of(full.get("year")),
            volumes=volumes_of(str(full.get("status", ""))),
            form=form_of(record),
            cover_url=image.get("original"),
            popularity=min(rating / 10, 1.0),
            url=record.get("url"),
            summary=plain(str(full.get("description") or "")),
        )
