"""MangaDex: often down; names in every language, with the MyAnimeList and AniList ids."""

from typing import Any, Final

import httpx

from shelfdrop.utils.text import is_latin, script_of
from shelfdrop.works.clients.http import get_json, year_of
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.types import Candidate, Family, Name, SourceName

MANGADEX: Final = "https://api.mangadex.org"
MANGADEX_LANGS: Final = {
    "en": "en",
    "fr": "fr",
    "ja": "ja",
    "ja-ro": "ja-ro",
    "ko": "ko",
    "zh": "zh",
}


class MangaDexClient:
    name: SourceName = "mangadex"
    families: frozenset[Family] = frozenset({"manga"})

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def search(self, query: str, family: Family) -> list[Candidate]:
        body = await get_json(
            self.http,
            f"{MANGADEX}/manga",
            params={"title": query, "limit": 8, "includes[]": "author"},
        )
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            raise SourceError("unexpected body")
        return [self.candidate_of(item) for item in body["data"]]

    def candidate_of(self, item: dict[str, Any]) -> Candidate:
        attrs = item.get("attributes") or {}
        names: list[Name] = []
        for lang, title in (attrs.get("title") or {}).items():
            names.append(Name(title=title, language=MANGADEX_LANGS.get(lang, lang)))
        for alt in attrs.get("altTitles") or []:
            for lang, title in alt.items():
                language = MANGADEX_LANGS.get(lang) or (
                    lang if is_latin(title) else script_of(title)
                )
                names.append(Name(title=title, language=language))
        authors = [
            r["attributes"]["name"]
            for r in item.get("relationships") or []
            if r.get("type") == "author" and (r.get("attributes") or {}).get("name")
        ]
        links = attrs.get("links") or {}
        external = {"myanimelist": str(links["mal"])} if links.get("mal") else {}
        if links.get("al"):
            external["anilist"] = str(links["al"])
        last = str(attrs.get("lastVolume") or "")
        return Candidate(
            source="mangadex",
            source_id=str(item["id"]),
            title=names[0].title if names else str(item["id"]),
            names=tuple(names),
            authors=tuple(dict.fromkeys(authors)),
            year=year_of(attrs.get("year")),
            volumes=int(last) if last.isdigit() else None,
            form="manga",
            external_ids=external,
            url=f"https://mangadex.org/title/{item['id']}",
        )
