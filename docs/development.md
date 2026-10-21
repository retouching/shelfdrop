# Development

The rules of the code are in `CLAUDE.md`; this page describes the code as it is.

## Module map
- `shelfdrop/main.py`: `create_app()` (the uvicorn factory: reads `Settings`, configures logging, creates the data directory) and `build_app(settings)` (routers, middlewares, error handlers, the pages, the container).
- `shelfdrop/config.py`: `Settings`.
- `shelfdrop/container.py`: `injectables(settings)`; `open_http` (the `httpx.AsyncClient` of the sources, with the User-Agent of `user_agent`), `new_work_sources` (the metadata clients, in the order of `unavailable`; MyAnimeList only with its Client ID).
- `shelfdrop/cli/main.py`: the `shelfdrop` command; `shelfdrop db upgrade` applies the migrations, `shelfdrop db check` compares the database with the models (exit 1 on a difference).
- `shelfdrop/db/`: `base.py` (`Base` and its naming convention), `engine.py` (`new_engine`, which sets WAL, the foreign keys and a 5 second wait on every SQLite connection; `open_engine`, `open_session`), `migrate.py` (`upgrade_database`, `check_database`), `models/` (`SourceAnswer`, `CachedWork`), `migrations/` (Alembic, batch mode for SQLite).
- `shelfdrop/works/`:
  - `service.py`: `WorkService` (`search`, `run_search`, `save`, `read_work`), `MetadataClient` (the protocol of a source), `WorkSources`.
  - `repository.py`: `WorkRepository`, the cache (`read_answers`, `save_answers`, `save_works`, `read_work`, `remove_expired`, `commit`).
  - `flights.py`: `SearchFlights` and `SourceHealth`, container singletons.
  - `merge.py`, `ranking.py`, `names.py`: the pure rules of [the work search](how-it-works.md#work-search).
  - `types.py`: `Candidate`, `Name`, `Work`, `NameChoice`, `WorkSearch`, `SearchOptions`, `Clock` and the aliases `Kind`, `Family`, `Form`, `SourceName`.
  - `exceptions.py`: `SourceError`, `QueryTooShortError`, `NoSourceAnsweredError`, `WorkNotFoundError`.
  - `clients/`: `mangaupdates.py`, `kitsu.py`, `myanimelist.py` (the official API, with a Client ID), `anilist.py`, `mangadex.py`, `bnf.py` (SRU, Dublin Core records), `openlibrary.py`, `wikidata.py`, and `http.py` (`get_json`, `post_json`, `get_text`: any failure becomes a `SourceError` named by a status or a class).
- `shelfdrop/http/`: `errors/` (`ErrorCode`, `ApiError`, the factories, the handlers, `ErrorResponse`), `middleware/` (one file per middleware), `dependencies.py` (`release_session`).
- `shelfdrop/logging/`: `configure_logging`, `JsonFormatter`, `RequestIdFilter`, `request_id_var`.
- `shelfdrop/modules/`: `health/`, `works/` (`router.py`, `schemas.py`, `errors.py`), `web/` (`web_router`: a file at the top of the build, or `index.html`).
- `shelfdrop/utils/`: `text.py` (`normalize`, `words`, `compact`, `script_of`, `is_latin`), `isbn.py` (`parse_isbn`, `isbn13_of`).

## Layers
A router calls its service and maps its domain exceptions to HTTP errors; a service holds the rules and calls its repository and its clients; a repository runs the queries and commits. `tests/unit/test_layers.py` checks the imports: the domain never imports a framework nor the HTTP layer, wireup stays in the composition and the routers, the routers never touch the database, the utilities import the standard library alone.

The two routes of the work search are `async`: the search waits on every source at once on the event loop, and its service runs the repository in the threadpool ([ADR 0007](adr/0007-work-search.md)).

## Database
Two tables, both caches: `source_answers` (the candidates a source gave for a family and a normalized text, a day) and `cached_works` (a merged work by its id, a week). Their rows are JSON written and read by `WorkRepository` through Pydantic `TypeAdapter`s of the types of `shelfdrop.works.types`.

## Tests
- `tests/unit/works/test_service.py`: the 9 recorded searches of `tests/unit/works/cases.py`, replayed from `tests/unit/works/fixtures/` (recorded on 2026-10-21 without a MyAnimeList Client ID, when AniList did not answer: its exchanges replay as failures), and the rules of the service with fake sources (`CountingClient`): the cache, the rest of a failed source, one run for two searches, the refusals.
- `tests/unit/works/support.py`: `RecordingTransport`, `ReplayTransport`, `FakeWorkRepository`, `FixedClock`, `new_service`.
- `tests/unit/works/record.py`: records the fixtures again (`uv run python -m tests.unit.works.record [slug ...]`).
- `tests/unit/test_main.py`: the application through `httpx.ASGITransport`.
- `tests/unit/test_naming.py`, `tests/unit/test_layers.py`, `tests/unit/db/test_migrate.py` (the chain of the revisions and the digest of each), `tests/unit/test_integration_parts.py` (the markers of the integration suite).

## Integration tests
`tests/integration/conftest.py` starts one stack per session, `shelfdrop-test-<random>`, from `docker/compose.yaml` and `docker/compose.test.yaml`: the real image of the API, its loopback port drawn at random, and `fake-sources`, WireMock 3.13.2, which the API reaches on the network `sources`, with no way out. The API sends every request of the metadata clients there (`SHELFDROP_SOURCES_ORIGIN`, `shelfdrop.works.clients.redirect.RedirectTransport`), its first origin in `X-Original-Origin`; the session loads into WireMock one stub per exchange recorded in `tests/unit/works/fixtures/` (`tests.integration.support.recorded_stubs`), a recorded failure replayed as a reset connection, and a request recorded with no stub gets a `404`. A failed source is not skipped there (`SHELFDROP_SOURCE_REST_SECONDS=0`), so that no test disturbs the next one. `tests/integration/support.py` holds `Stack` (its logs, `exec_api`), `FakeSources` (load stubs, count requests, list the unmatched ones) and `compose`.

### Parts of the integration suite

| Part | Test files | Code that calls for it |
|---|---|---|
| `security` | `test_errors.py`, `test_health.py`, `test_http_headers.py`, `test_logging.py`, `test_migrations.py` | `shelfdrop/http/`, `shelfdrop/logging/`, `shelfdrop/main.py`, `shelfdrop/config.py`, `shelfdrop/container.py`, `shelfdrop/db/`, `shelfdrop/cli/`, `docker/` |
| `pages` | `test_pages.py` | `shelfdrop/modules/web/`, `web/`, `docker/api.Dockerfile` |
| `works` | `test_work_search.py`, `test_work_sources.py`, `test_work_names.py` | `shelfdrop/works/`, `shelfdrop/modules/works/`, `tests/unit/works/fixtures/` |

#### Blocks

| Block | Part | Subject | Code that calls for it |
|---|---|---|---|
| `security_errors` | `security` | the error bodies (`test_errors.py`) | `shelfdrop/http/errors/`, the `errors.py` of a module |
| `security_health` | `security` | the liveness probe (`test_health.py`) | `shelfdrop/modules/health/`, the access log |
| `security_headers` | `security` | the response headers (`test_http_headers.py`) | `shelfdrop/http/middleware/`, the uvicorn command of the image |
| `security_logging` | `security` | the logs of the API (`test_logging.py`) | `shelfdrop/logging/`, the access log, the logs of `shelfdrop/works/service.py` |
| `security_migrations` | `security` | the migrations at head, a restart keeps the data (`test_migrations.py`); it restarts the API, last of its part | `shelfdrop/db/`, `shelfdrop/cli/`, the command of the image |
| `pages` | `pages` | the pages, their files, the prefix of the API (`test_pages.py`) | `shelfdrop/modules/web/`, `web/` |
| `works_search` | `works` | the recorded searches of `tests/unit/works/cases.py`, through the API (`test_work_search.py`) | `shelfdrop/works/`, `shelfdrop/modules/works/` |
| `works_sources` | `works` | the failed sources, the cache, one run for two searches (`test_work_sources.py`) | `shelfdrop/works/service.py`, `shelfdrop/works/flights.py`, `shelfdrop/works/repository.py` |
| `works_names_language` | `works` | the languages of the names, the ones checked by default (`test_work_names.py`) | `shelfdrop/works/names.py`, `shelfdrop/works/merge.py`, the names of a client |
