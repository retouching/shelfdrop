"""Catalogue of the Bibliothèque nationale de France (SRU, Dublin Core records).

The French edition of a book or a manga: its French title, its translator-free authors, its ISBNs
and, for a series, how many volumes came out in France. Each volume is a record
("Dusk maiden of amnesia. 10 / Maybe"); records of the same title are grouped into one candidate.
"""

import re
from dataclasses import dataclass, field
from typing import Final
from xml.etree.ElementTree import Element

import httpx
from defusedxml.ElementTree import ParseError, fromstring

from shelfdrop.utils.isbn import isbn13_of, parse_isbn
from shelfdrop.utils.text import normalize
from shelfdrop.works.clients.http import get_text
from shelfdrop.works.exceptions import SourceError
from shelfdrop.works.names import person_name, surname
from shelfdrop.works.types import Candidate, Family, Name, SourceName

API = "https://catalogue.bnf.fr/api/SRU"
NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "dc": "http://purl.org/dc/elements/1.1/",
}
VOLUME = re.compile(
    r"^(?P<base>.{3,}?)(?:\.\s*|\s+)(?:T(?:ome)?\.?\s*)?(?P<n>\d{1,3})(?P<half>\.\d+)?"
    r"(?=\s*(?:$|[-:(,]))",
    re.IGNORECASE,
)
QUOTED_SERIES: Final = re.compile(r'^["«]\s*(?P<name>[^"»]+?)\s*["»]\s*:')
PART = re.compile(
    r"^(?P<base>.+?)\.\s*(?:Partie|Tomes|Coffret|Intégrale|Volume)\b.*$", re.IGNORECASE
)
EDITION_NOTE = re.compile(
    r"\s*\(\[?(?:[ÉE]d\.|[ÉE]dition|\d+e [ée]dition)[^)]*\).*$", re.IGNORECASE
)
AUTHOR_ROLES = ("auteur", "scénariste", "dessinateur", "illustrateur", "adaptateur")


@dataclass
class Group:
    title: str
    authors: list[str] = field(default_factory=list)
    volumes: set[int] = field(default_factory=set)
    isbns: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    french: bool = False
    ark: str | None = None
    records: int = 0


def quoted(text: str) -> str:
    return '"' + text.replace('"', " ").replace("\\", " ") + '"'


def split_title(raw: str) -> tuple[str, int | None]:
    """'Dusk maiden of amnesia. 10 / Maybe' -> ('Dusk maiden of amnesia', 10).

    A subtitle stays when a volume number follows it ('Kaguya-sama : love is war. 17' is a
    series) and goes otherwise ('Ne cède jamais : libère ton mental' is one book). A quoted name
    before a subtitle is the series: '"Horimiya" : memorial book page 100' is a Horimiya book,
    not volume 100. Half volumes (10.5, fan books) count for the series but not as a volume.
    """
    title = raw.split(" / ", 1)[0].strip()
    title = EDITION_NOTE.sub("", title)
    quoted = QUOTED_SERIES.match(title)
    title = (quoted.group("name") if quoted else title).strip(' .:"«»')
    part = PART.match(title)
    if part:
        return part.group("base").strip(' .:"«»'), None
    found = VOLUME.match(title)
    if found:
        base = found.group("base").strip(' .:"«»')
        return base, None if found.group("half") else int(found.group("n"))
    return title.split(" : ", 1)[0].strip(' .:"«»'), None


def author_of(raw: str) -> str | None:
    """'Fujimoto, Tatsuki. Auteur du texte' -> 'Tatsuki Fujimoto'; translators are skipped."""
    name, _, role = raw.rpartition(". ")
    if not name:
        return None
    if not role.lower().startswith(AUTHOR_ROLES):
        return None
    return person_name(name)


class BnfClient:
    name: SourceName = "bnf"
    families: frozenset[Family] = frozenset({"manga", "book"})

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def search(self, query: str, family: Family) -> list[Candidate]:
        isbn = parse_isbn(query)
        if isbn:
            cql = f"bib.isbn all {quoted(isbn)}"
        elif family == "manga":
            cql = f"bib.title all {quoted(query)}"
        else:
            cql = f"bib.title all {quoted(query)} or bib.author all {quoted(query)}"
        text = await get_text(
            self.http,
            API,
            params={
                "version": "1.2",
                "operation": "searchRetrieve",
                "query": cql,
                "recordSchema": "dublincore",
                "maximumRecords": 50,
            },
        )
        try:
            root = fromstring(text)
        except ParseError as exc:
            raise SourceError("invalid XML") from exc
        return self.candidates(root)

    def candidates(self, root: Element) -> list[Candidate]:
        groups: dict[str, Group] = {}
        for record in root.iterfind(".//srw:recordData/*", NS):
            types = [t.text or "" for t in record.iterfind("dc:type", NS)]
            if types and not any(t in ("text", "texte imprimé") for t in types):
                continue  # films, records, kits...
            raw_title = record.findtext("dc:title", "", NS)
            if not raw_title:
                continue
            title, volume = split_title(raw_title)
            authors = [
                a for a in (author_of(c.text or "") for c in record.iterfind("dc:creator", NS)) if a
            ]
            key = f"{normalize(title)}|{surname(authors[0]) if authors else ''}"
            group = groups.setdefault(key, Group(title=title))
            group.records += 1
            for author in authors:
                if author not in group.authors:
                    group.authors.append(author)
            if volume is not None:
                group.volumes.add(volume)
            group.french |= any(
                (lang.text or "") == "fre" for lang in record.iterfind("dc:language", NS)
            )
            for identifier in record.iterfind("dc:identifier", NS):
                value = identifier.text or ""
                if value.startswith("ISBN"):
                    isbn = parse_isbn(value.removeprefix("ISBN").strip())
                    if isbn and isbn13_of(isbn) not in group.isbns:
                        group.isbns.append(isbn13_of(isbn))
                elif "ark:/" in value and group.ark is None:
                    group.ark = value.strip()
            date = record.findtext("dc:date", "", NS)[:4]
            if date.isdigit():
                group.years.append(int(date))
        return [self.candidate_of(g) for g in groups.values() if g.french]

    def candidate_of(self, group: Group) -> Candidate:
        return Candidate(
            source="bnf",
            source_id=group.ark or group.title,
            title=group.title,
            names=(Name(title=group.title, language="fr"),),
            authors=tuple(group.authors),
            year=min(group.years) if group.years else None,
            volumes_fr=max(group.volumes) if group.volumes else None,
            isbns=tuple(group.isbns[:40]),
            popularity=min(group.records / 20, 1.0),
            url=group.ark,
        )
