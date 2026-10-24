"""Open Library (search.json): books and their editions, with each edition's language and ISBNs.

With `lang=fr`, the edition shown under a work is the French one when it exists: "Can't Hurt Me"
comes back with its edition "Plus rien ne pourra me blesser".
"""

from typing import Any

import anyio
import httpx

from shelfdrop.utils.isbn import isbn13_of, parse_isbn
from shelfdrop.works.clients.http import get_json
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.types import Candidate, Family, Name, SourceName

API = "https://openlibrary.org/search.json"
COVERS = "https://covers.openlibrary.org/b/id/{}-M.jpg"
EDITIONS = "https://openlibrary.org/works/{}/editions.json"
FRENCH_LOOKUPS = 3
# The French editions are looked for this long at most: past it, the works come without them
# rather than the whole source missing the search.
FRENCH_LOOKUP_SECONDS = 3.0
FIELDS = ",".join(
    [
        "key",
        "title",
        "author_name",
        "first_publish_year",
        "isbn",
        "language",
        "cover_i",
        "edition_count",
        "editions",
        "editions.key",
        "editions.title",
        "editions.language",
        "editions.isbn",
    ]
)
LANGS = {"eng": "en", "fre": "fr", "jpn": "ja", "spa": "es", "ger": "de", "ita": "it"}


class OpenLibraryClient:
    name: SourceName = "openlibrary"
    families: frozenset[Family] = frozenset({"book"})

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def search(self, query: str, family: Family) -> list[Candidate]:
        isbn = parse_isbn(query)
        params: dict[str, str | int] = {"fields": FIELDS, "lang": "fr", "limit": 8}
        if isbn:
            params["isbn"] = isbn
        else:
            params["q"] = query
        body = await get_json(self.http, API, params=params)
        if not isinstance(body, dict) or not isinstance(body.get("docs"), list):
            raise SourceError("unexpected body")
        docs = [doc for doc in body["docs"] if doc.get("title")]
        french: dict[str, dict[str, Any]] = {}

        async def lookup(work_key: str) -> None:
            # The search shows the edition that matched the query; the French one, if any, is
            # among the other editions of the work.
            try:
                editions = await get_json(
                    self.http,
                    EDITIONS.format(work_key.removeprefix("/works/")),
                    params={"limit": 100},
                )
            except SourceError:
                return
            for entry in editions.get("entries", []) if isinstance(editions, dict) else []:
                if any("/fre" in str(lang.get("key")) for lang in entry.get("languages") or []):
                    french[work_key] = entry
                    return

        with anyio.move_on_after(FRENCH_LOOKUP_SECONDS):
            async with anyio.create_task_group() as group:
                for doc in docs[:FRENCH_LOOKUPS]:
                    if not self.french_edition(doc):
                        group.start_soon(lookup, str(doc["key"]))
        return [self.candidate_of(doc, french.get(str(doc["key"]))) for doc in docs]

    @staticmethod
    def french_edition(doc: dict[str, Any]) -> bool:
        editions = (doc.get("editions") or {}).get("docs") or []
        return any("fre" in (e.get("language") or []) for e in editions)

    def candidate_of(self, doc: dict[str, Any], french: dict[str, Any] | None) -> Candidate:
        languages = doc.get("language") or []
        original = LANGS.get(languages[0], "latin") if len(languages) == 1 else "latin"
        names = [Name(title=doc["title"], language=original)]
        isbns = [isbn13_of(i) for i in (parse_isbn(x) for x in doc.get("isbn") or []) if i]
        for edition in (doc.get("editions") or {}).get("docs") or []:
            title = edition.get("title")
            if title and "fre" in (edition.get("language") or []):
                names.append(Name(title=title, language="fr"))
                isbns += [
                    isbn13_of(i) for i in (parse_isbn(x) for x in edition.get("isbn") or []) if i
                ]
        if french and french.get("title"):
            names.append(Name(title=french["title"], language="fr"))
            for raw in [*(french.get("isbn_13") or []), *(french.get("isbn_10") or [])]:
                isbn = parse_isbn(raw)
                if isbn:
                    isbns.append(isbn13_of(isbn))
        cover = doc.get("cover_i")
        return Candidate(
            source="openlibrary",
            source_id=str(doc["key"]).removeprefix("/works/"),
            title=doc["title"],
            names=tuple(names),
            authors=tuple(dict.fromkeys(doc.get("author_name") or [])),
            year=doc.get("first_publish_year"),
            cover_url=COVERS.format(cover) if cover else None,
            isbns=tuple(dict.fromkeys(isbns))[:40],
            popularity=min(int(doc.get("edition_count") or 0) / 40, 1.0),
            url=f"https://openlibrary.org{doc['key']}",
        )
