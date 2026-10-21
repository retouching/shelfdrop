"""Kitsu (kitsu.io/api/edge): English, Japanese and romaji titles, abbreviations, volume count,
and the AniList and MyAnimeList ids of the same manga (the pivot of the merge)."""

from typing import Any

import httpx

from shelfdrop.utils.text import is_latin, script_of
from shelfdrop.works.clients.http import get_json, year_of
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.types import Candidate, Family, Form, Name, SourceName

API = "https://kitsu.io/api/edge"

FORMS: dict[str, Form] = {
    "manga": "manga",
    "manhwa": "manga",
    "manhua": "manga",
    "oel": "manga",
    "novel": "novel",
    "oneshot": "oneshot",
    "doujin": "doujinshi",
}
LANGS = {"en": "en", "en_us": "en", "en_jp": "ja-ro", "ja_jp": "ja", "fr": "fr", "fr_fr": "fr"}
MAPPINGS = {"myanimelist/manga": "myanimelist", "anilist/manga": "anilist"}


class KitsuClient:
    name: SourceName = "kitsu"
    families: frozenset[Family] = frozenset({"manga"})

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def search(self, query: str, family: Family) -> list[Candidate]:
        body = await get_json(
            self.http,
            f"{API}/manga",
            params={
                "filter[text]": query,
                "page[limit]": 8,
                "include": "mappings",
                "fields[mappings]": "externalSite,externalId",
            },
            headers={"Accept": "application/vnd.api+json"},
        )
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            raise SourceError("unexpected body")
        mappings: dict[str, tuple[str, str]] = {}
        for item in body.get("included", []):
            attrs = item.get("attributes", {})
            mappings[str(item.get("id"))] = (
                str(attrs.get("externalSite")),
                str(attrs.get("externalId")),
            )
        return [self.candidate_of(item, mappings) for item in body["data"]]

    def candidate_of(self, item: dict[str, Any], mappings: dict[str, tuple[str, str]]) -> Candidate:
        attrs = item["attributes"]
        names: list[Name] = []
        for key, title in (attrs.get("titles") or {}).items():
            if title:
                names.append(Name(title=title, language=LANGS.get(key, script_of(title))))
        canonical = attrs.get("canonicalTitle") or (names[0].title if names else "")
        if canonical and all(n.title != canonical for n in names):
            names.insert(0, Name(title=canonical, language="latin"))
        for alt in attrs.get("abbreviatedTitles") or []:
            if alt:
                names.append(Name(title=alt, language="latin" if is_latin(alt) else script_of(alt)))
        external: dict[str, str] = {}
        for ref in (item.get("relationships", {}).get("mappings", {}) or {}).get("data") or []:
            site, external_id = mappings.get(str(ref.get("id")), ("", ""))
            if site in MAPPINGS:
                external[MAPPINGS[site]] = external_id
        users = int(attrs.get("userCount") or 0)
        poster = attrs.get("posterImage") or {}
        return Candidate(
            source="kitsu",
            source_id=str(item["id"]),
            title=canonical,
            names=tuple(names),
            year=year_of(attrs.get("startDate")),
            volumes=attrs.get("volumeCount") or None,
            form=FORMS.get(str(attrs.get("subtype", "")).lower(), "other"),
            cover_url=poster.get("small") or poster.get("original"),
            external_ids=external,
            popularity=min(users / 50_000, 1.0),
            url=f"https://kitsu.app/manga/{attrs.get('slug') or item['id']}",
        )
