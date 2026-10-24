"""Response schemas of the works module."""

from pydantic import BaseModel, ConfigDict, Field

from shelfdrop.works.types import Form, Kind, SourceName


class NameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    # "fr", "en", "ja-ro" (romaji), "ja"... or "latin" when the language is not known.
    language: str
    # Searched on Prowlarr unless unchecked.
    checked: bool
    # The sources that gave it, the most trusted first (the setting `search.source_order`), and
    # the first of them; none (null) in a work found before the sources of its names were kept.
    sources: list[SourceName]
    source: SourceName | None


class WorkPartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    # Its name on the shelf when it was found alone.
    title: str
    authors: list[str]
    sources: list[SourceName]


class WorkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    # The name in the library: the title of the French edition when there is one.
    shelf_name: str
    authors: list[str]
    year: int | None
    # Volumes of the original edition.
    volumes: int | None
    # Volumes published in France.
    volumes_fr: int | None
    form: Form
    names: list[NameRead]
    sources: list[SourceName]
    cover_url: str | None
    isbns: list[str]
    # The page of the work at each source, by source.
    links: dict[str, str]
    # The merge by hand it comes from, and the works that merge joined (none otherwise).
    merge_id: int | None
    parts: list[WorkPartRead]


class WorkSearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    kind: Kind
    works: list[WorkRead]
    # Novels, anthologies, dōjinshi... of a manga search, shown apart.
    other_forms: list[WorkRead]
    # The sources that did not answer: the works come from the others.
    unavailable: list[SourceName]


class WorkMergeCreate(BaseModel):
    # The kind of the search the works were found by.
    kind: Kind
    # The ids of the works to join, a merge among them (its id) to add to it.
    work_ids: list[str] = Field(min_length=2, max_length=20)
    # The name on the shelf of the work they make.
    shelf_name: str = Field(min_length=1, max_length=300)


class WorkMergeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # `manga` or `book`: the searches it applies to.
    family: str
    # The keys of the members joined, `<source>:<id at that source>`.
    keys: list[str]
    shelf_name: str
