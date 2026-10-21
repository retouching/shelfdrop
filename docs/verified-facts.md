# Verified facts

Behaviours of the metadata sources, libraries and tools this code relies on. Each fact has an ID (`Fnn`, never reused), its evidence, the test that pins it and a re-verification trigger. A source has no version: its heading names the endpoint, and its facts are re-verified when the fixtures are recorded again (`uv run python -m tests.unit.works.record`) or when a recorded search fails. A library heading names the version of `uv.lock`; a version change updates the heading in the same commit and re-reads the facts no test pins.

Next fact ID: F13.

## Metadata sources

### MangaUpdates (api.mangaupdates.com/v1)

- **F01** `POST /series/search` matches the associated names too, French ones included, and `GET /series/{id}` lists them in `associated` as `{"title"}` alone: no language, some with it in brackets ("Atelier of Witch Hat (Indonesian)"). `shelfdrop.works.clients.mangaupdates` gives them the language `latin` or the one of their script; `shelfdrop.works.names.language_of` tells the language of some after the merge (Turkish, Polish, Indonesian names among them in `atelier-des-sorciers.json`).
  - Evidence: the fixtures `chainsaw-man.json` and `atelier-des-sorciers.json` (recorded 2026-10-21).
  - Pinned by: `tests/unit/works/test_service.py::test_recorded_search`, `tests/unit/works/test_names.py::test_language_of`
  - Re-verify: on recording.

### Kitsu (kitsu.io/api/edge)

- **F02** `GET /manga?include=mappings` returns, in `included`, the ids of the same work at other sites (`externalSite` `myanimelist/manga`, `anilist/manga`...), which merge its candidate with theirs.
  - Evidence: the fixture `chainsaw-man.json`.
  - Pinned by: `tests/unit/works/test_service.py::test_recorded_search`
  - Re-verify: on recording.

### BnF catalogue (catalogue.bnf.fr/api/SRU)

- **F03** `searchRetrieve` with `recordSchema=dublincore` answers one record per volume of a series, its `dc:title` as `<series>. <n> / <authors>` (`Dusk maiden of amnesia. 10 / Maybe`), in catalogue case; editions and boxes add a note in brackets or parentheses, and a fan book is numbered `10.5`.
  - Evidence: the fixtures `dusk-maiden.json`, `chainsaw-man.json`; the answer of `bib.title all "horimiya"` read on 2026-10-21.
  - Pinned by: `tests/unit/works/clients/test_bnf.py::test_bnf_title`
  - Re-verify: on recording.
- **F04** A translated book's record does not give its original title: "Ne cède jamais" (Goggins, *Never Finished*) is found, but nothing ties it to the English work.
  - Evidence: the searches of "Never Finished" and "Ne cède jamais" in the BnF, Open Library and Wikidata on 2026-10-21.
  - Pinned by: none
  - Re-verify: on recording.

### Open Library (openlibrary.org)

- **F05** `search.json` gives, for a work, a few of its editions; the French one is often missing there and found among `/works/{id}/editions.json` (`languages` `/languages/fre`). `shelfdrop.works.clients.openlibrary` reads the editions of its first 3 works (`FRENCH_LOOKUPS`).
  - Evidence: the fixture `can-t-hurt-me.json` ("Can't Hurt Me" → "Plus rien ne pourra me blesser").
  - Pinned by: `tests/unit/works/test_service.py::test_recorded_search`
  - Re-verify: on recording.

### AniList, MangaDex

- **F06** On 2026-10-21 AniList answered `403` "The AniList API has been temporarily disabled"; MangaDex answered. The fixtures replay that failure.
  - Evidence: the fixtures of every manga case.
  - Pinned by: `tests/unit/works/test_service.py::test_down_sources_are_named`
  - Re-verify: on recording.

## Pinned components

### sqlalchemy 2.1.5, alembic 1.20.0

- **F07** SQLite cannot alter most of a table in place; Alembic's batch mode (`render_as_batch=True` in `shelfdrop/db/migrations/env.py`) copies the table instead.
  - Evidence: Alembic documentation, "Running “Batch” Migrations for SQLite and Other Databases".
  - Pinned by: none
  - Re-verify: on version change.

### wireup 2.13.0

- **F08** With `create_async_container` and `setup(..., middleware_mode=True)`, the scope of a request closes on the event loop after the response: a session closed there would block it. `release_session`, a sync dependency of every route, closes the session in the threadpool first.
  - Evidence: Source: `wireup/integration/starlette.py` `WireupAsgiMiddleware.__call__` (`async with ... enter_scope(...)` around the whole application call).
  - Pinned by: none
  - Re-verify: on version change.

### wiremock/wiremock 3.13.2 (sha256:0d4ecb3e..., observed on 2026-10-21; the test stack alone)

- **F09** A stub matches `queryParameters` whatever their order, on their decoded values; `bodyPatterns` `equalToJson` compares JSON values, not the text; a request no stub matches gets a `404`, and is listed by `GET /__admin/requests/unmatched`.
  - Evidence: WireMock documentation, "Request Matching"; the runs of `tests/integration/test_work_search.py`.
  - Pinned by: `tests/integration/test_work_search.py::test_every_request_of_the_searches_was_recorded`, `tests/integration/test_work_sources.py::test_no_source_answering_is_a_503`
  - Re-verify: on version change.
- **F10** `POST /__admin/mappings/import` loads stubs over the running ones with `duplicatePolicy` `OVERWRITE`, and answers `500` (a `NullPointerException`) when `importOptions` has no `deleteAllNotInImport`; `POST /__admin/requests/count` counts the journal entries that match a request pattern.
  - Evidence: WireMock documentation, "Administration API".
  - Pinned by: `tests/integration/test_work_sources.py::test_two_identical_searches_at_once_share_one_run`
  - Re-verify: on version change.

### docker compose 2.26 and later

- **F11** The YAML tag `!override` in a file given after another replaces a list (`ports`) instead of adding to it; `docker compose port` prints `127.0.0.1:<port>` of a port published as `127.0.0.1::8000`.
  - Evidence: Compose documentation, "Merge and override"; the start of the test stack.
  - Pinned by: the fixture `stack` of `tests/integration/conftest.py`
  - Re-verify: when Compose changes.

### python:3.13-slim-trixie (the image of the API)

- **F12** The image has no `/etc/mime.types`: `mimetypes` knows no `.woff2`, and Starlette would serve a font as `application/octet-stream`. `shelfdrop.modules.web.router.web_router` adds `font/woff2`.
  - Evidence: `tests/integration/test_pages.py::test_the_icon_and_the_font_are_served` failed without it on 2026-10-21.
  - Pinned by: `tests/integration/test_pages.py::test_the_icon_and_the_font_are_served`
  - Re-verify: when the base image changes.
