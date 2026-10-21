"""AniList (GraphQL): an optional manga source, often down; the others suffice."""

from typing import Any

import httpx

from shelfdrop.utils.text import is_latin, script_of
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.types import Candidate, Family, Form, Name, SourceName

ANILIST = "https://graphql.anilist.co"

QUERY = """
query ($search: String) {
  Page(perPage: 8) {
    media(search: $search, type: MANGA) {
      id idMal format volumes popularity siteUrl
      title { romaji english native }
      synonyms
      startDate { year }
      coverImage { medium }
      staff(perPage: 4, sort: RELEVANCE) { edges { role node { name { full } } } }
    }
  }
}
"""

ANILIST_FORMS: dict[str, Form] = {"MANGA": "manga", "NOVEL": "novel", "ONE_SHOT": "oneshot"}


def latin_or_script(title: str) -> str:
    return "latin" if is_latin(title) else script_of(title)


class AniListClient:
    name: SourceName = "anilist"
    families: frozenset[Family] = frozenset({"manga"})

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def search(self, query: str, family: Family) -> list[Candidate]:
        try:
            response = await self.http.post(
                ANILIST, json={"query": QUERY, "variables": {"search": query}}
            )
        except httpx.HTTPError as exc:
            raise SourceError(type(exc).__name__) from exc
        if response.status_code != 200:
            raise SourceError(f"HTTP {response.status_code}")
        body = response.json()
        media = ((body.get("data") or {}).get("Page") or {}).get("media")
        if not isinstance(media, list):
            raise SourceError("unexpected body")
        return [self.candidate_of(m) for m in media]

    def candidate_of(self, media: dict[str, Any]) -> Candidate:
        title = media.get("title") or {}
        names: list[Name] = []
        for key, language in (("english", "en"), ("romaji", "ja-ro"), ("native", "ja")):
            if title.get(key):
                names.append(Name(title=title[key], language=language))
        names += [Name(title=s, language=latin_or_script(s)) for s in media.get("synonyms") or []]
        authors = []
        for edge in (media.get("staff") or {}).get("edges") or []:
            role = str(edge.get("role", "")).lower()
            full = ((edge.get("node") or {}).get("name") or {}).get("full")
            if full and ("story" in role or "art" in role) and full not in authors:
                authors.append(full)
        external = {"myanimelist": str(media["idMal"])} if media.get("idMal") else {}
        return Candidate(
            source="anilist",
            source_id=str(media["id"]),
            title=title.get("english") or title.get("romaji") or names[0].title,
            names=tuple(names),
            authors=tuple(authors),
            year=(media.get("startDate") or {}).get("year"),
            volumes=media.get("volumes") or None,
            form=ANILIST_FORMS.get(str(media.get("format")), "other"),
            cover_url=(media.get("coverImage") or {}).get("medium"),
            external_ids=external,
            popularity=min(int(media.get("popularity") or 0) / 200_000, 1.0),
            url=media.get("siteUrl"),
        )
