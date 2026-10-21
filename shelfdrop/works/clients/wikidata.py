"""Wikidata: the title of a work in each language (French included), its authors and the ids of
the same work at MyAnimeList and Open Library. A complement: many books have no French label."""

from typing import Any

import anyio
import httpx

from shelfdrop.works.clients.http import get_json, year_of
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.types import Candidate, Family, Form, Name, SourceName

API = "https://www.wikidata.org/w/api.php"

# instance of (P31) accepted, by family
MANGA_TYPES = {"Q21198342": "manga", "Q8274": "manga", "Q747381": "novel", "Q104213567": "novel"}
BOOK_TYPES = {
    "Q7725634": "other",  # literary work
    "Q47461344": "other",  # written work
    "Q571": "other",  # book
    "Q8261": "novel",
    "Q277759": "other",  # book series
    "Q1667921": "novel",  # novel series
    "Q112983": "other",  # autobiography
}
LANGS = ("fr", "en", "ja")
P_INSTANCE, P_AUTHOR, P_DATE, P_MAL, P_OPENLIBRARY = "P31", "P50", "P577", "P4087", "P648"
P_ISBN13, P_ISBN10 = "P212", "P957"


def claim_ids(entity: dict[str, Any], prop: str) -> list[str]:
    found = []
    for claim in (entity.get("claims") or {}).get(prop, []):
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(value, dict) and "id" in value:
            found.append(str(value["id"]))
        elif isinstance(value, dict) and "time" in value:
            found.append(str(value["time"]).lstrip("+"))
        elif isinstance(value, str):
            found.append(value)
    return found


class WikidataClient:
    name: SourceName = "wikidata"
    families: frozenset[Family] = frozenset({"manga", "book"})

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def search(self, query: str, family: Family) -> list[Candidate]:
        hits: dict[str, list[str]] = {"fr": [], "en": []}
        failures: list[SourceError] = []

        async def lookup(language: str) -> None:
            try:
                body = await get_json(
                    self.http,
                    API,
                    params={
                        "action": "wbsearchentities",
                        "search": query,
                        "language": language,
                        "uselang": "fr",
                        "type": "item",
                        "limit": 8,
                        "format": "json",
                    },
                )
            except SourceError as exc:
                failures.append(exc)
                return
            for hit in body.get("search", []) if isinstance(body, dict) else []:
                hits[language].append(str(hit["id"]))

        async with anyio.create_task_group() as group:
            group.start_soon(lookup, "fr")
            group.start_soon(lookup, "en")
        if len(failures) == 2:
            raise failures[0]
        ids = list(dict.fromkeys([*hits["fr"], *hits["en"]]))  # stable order, whatever came first
        if not ids:
            return []
        entities = await self.fetch_entities(ids, "labels|aliases|claims")
        allowed = MANGA_TYPES if family == "manga" else BOOK_TYPES
        works = []
        for entity_id in ids:
            entity = entities.get(entity_id)
            if not entity:
                continue
            kinds = [k for k in claim_ids(entity, P_INSTANCE) if k in allowed]
            if kinds:
                works.append((entity, allowed[kinds[0]]))
        author_ids = sorted({a for e, _ in works for a in claim_ids(e, P_AUTHOR)})
        authors = await self.fetch_entities(author_ids[:40], "labels") if author_ids else {}
        return [self.candidate_of(e, form, authors) for e, form in works]

    async def fetch_entities(self, ids: list[str], props: str) -> dict[str, Any]:
        body = await get_json(
            self.http,
            API,
            params={
                "action": "wbgetentities",
                "ids": "|".join(ids[:50]),
                "props": props,
                "languages": "|".join(LANGS),
                "format": "json",
            },
        )
        if not isinstance(body, dict) or not isinstance(body.get("entities"), dict):
            raise SourceError("unexpected body")
        entities: dict[str, Any] = body["entities"]
        return entities

    def candidate_of(self, entity: dict[str, Any], form: str, authors: dict[str, Any]) -> Candidate:
        names: list[Name] = []
        labels = entity.get("labels") or {}
        for language in LANGS:
            if language in labels:
                names.append(Name(title=labels[language]["value"], language=language))
        for language in ("fr", "en"):
            for alias in (entity.get("aliases") or {}).get(language, []):
                names.append(Name(title=alias["value"], language=language))
        label: dict[str, Any] = labels.get("en") or labels.get("fr") or {}
        if not label and labels:
            label = next(iter(labels.values()))
        title = str(label.get("value") or entity["id"])
        author_names: list[str] = []
        for author_id in claim_ids(entity, P_AUTHOR):
            author_labels = (authors.get(author_id) or {}).get("labels") or {}
            author = (author_labels.get("fr") or author_labels.get("en") or {}).get("value")
            if author:
                author_names.append(str(author))
        external = {}
        if mal := claim_ids(entity, P_MAL):
            external["myanimelist"] = mal[0]
        if openlibrary := claim_ids(entity, P_OPENLIBRARY):
            external["openlibrary"] = openlibrary[0]
        isbns = [i.replace("-", "") for i in claim_ids(entity, P_ISBN13)]
        dates = claim_ids(entity, P_DATE)
        form_value: Form = "novel" if form == "novel" else "manga" if form == "manga" else "other"
        return Candidate(
            source="wikidata",
            source_id=entity["id"],
            title=title,
            names=tuple(names),
            authors=tuple(author_names),
            year=year_of(dates[0]) if dates else None,
            form=form_value,
            isbns=tuple(isbns),
            external_ids=external,
            url=f"https://www.wikidata.org/wiki/{entity['id']}",
        )
