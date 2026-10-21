"""MyAnimeList: its official API v2, with a Client ID; never a third-party mirror (ADR 0007).

It gives the English and Japanese titles, the synonyms, the authors, the volume count and the
type. The MyAnimeList id is the pivot of the merge: Kitsu, AniList and MangaDex all give it.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from shelfdrop.utils.text import is_latin, script_of
from shelfdrop.works.clients.http import get_json, year_of
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.types import Candidate, Family, Form, Name, SourceName

OFFICIAL = "https://api.myanimelist.net/v2"

FORMS: dict[str, Form] = {
    "manga": "manga",
    "manhwa": "manga",
    "manhua": "manga",
    "oel": "manga",
    "one-shot": "oneshot",
    "one_shot": "oneshot",
    "doujinshi": "doujinshi",
    "doujin": "doujinshi",
    "novel": "novel",
    "light novel": "novel",
    "light_novel": "novel",
}


def latin_or_script(title: str) -> str:
    return "latin" if is_latin(title) else script_of(title)


class MyAnimeListClient:
    name: SourceName = "myanimelist"
    families: frozenset[Family] = frozenset({"manga"})

    def __init__(
        self, http: httpx.AsyncClient, client_id: Callable[[], Awaitable[str | None]]
    ) -> None:
        self.http = http
        # Read at each search, from the settings; sent in a header, never in the address: an
        # address may be logged.
        self.client_id = client_id

    async def search(self, query: str, family: Family) -> list[Candidate]:
        return await self.from_api(query)

    async def from_api(self, query: str) -> list[Candidate]:
        client_id = await self.client_id()
        if not client_id:
            raise SourceError("no client id")
        body = await get_json(
            self.http,
            f"{OFFICIAL}/manga",
            params={
                "q": query[:64],
                "limit": 8,
                "fields": "alternative_titles,num_volumes,authors{first_name,last_name},"
                "media_type,start_date,num_list_users,main_picture",
            },
            headers={"X-MAL-CLIENT-ID": client_id},
        )
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            raise SourceError("unexpected body")
        return [self.from_official(entry["node"]) for entry in body["data"]]

    def from_official(self, node: dict[str, Any]) -> Candidate:
        alt = node.get("alternative_titles") or {}
        names = [Name(title=node["title"], language="ja-ro")]
        if alt.get("en"):
            names.append(Name(title=alt["en"], language="en"))
        if alt.get("ja"):
            names.append(Name(title=alt["ja"], language="ja"))
        names += [
            Name(title=s, language=latin_or_script(s)) for s in alt.get("synonyms") or [] if s
        ]
        authors = []
        for entry in node.get("authors") or []:
            person = entry.get("node") or {}
            full = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
            if full:
                authors.append(full)
        users = int(node.get("num_list_users") or 0)
        return Candidate(
            source="myanimelist",
            source_id=str(node["id"]),
            title=alt.get("en") or node["title"],
            names=tuple(names),
            authors=tuple(authors),
            year=year_of(node.get("start_date")),
            volumes=node.get("num_volumes") or None,
            form=FORMS.get(str(node.get("media_type", "")).lower(), "other"),
            cover_url=(node.get("main_picture") or {}).get("medium"),
            popularity=min(users / 500_000, 1.0),
            url=f"https://myanimelist.net/manga/{node['id']}",
        )
