"""Response schemas of the works module."""

from pydantic import BaseModel, ConfigDict

from shelfdrop.works.types import Form, Kind, SourceName


class NameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    # "fr", "en", "ja-ro" (romaji), "ja"... or "latin" when the language is not known.
    language: str
    # Searched on Prowlarr unless unchecked.
    checked: bool


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


class WorkSearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    kind: Kind
    works: list[WorkRead]
    # Novels, anthologies, dōjinshi... of a manga search, shown apart.
    other_forms: list[WorkRead]
    # The sources that did not answer: the works come from the others.
    unavailable: list[SourceName]
