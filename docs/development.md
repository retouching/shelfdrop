# Development

The rules of the code are in `CLAUDE.md`; this page describes the code as it is.

## Module map
- `shelfdrop/main.py`: `create_app()` (the uvicorn factory: reads `Settings`, configures logging, creates the data directory) and `build_app(settings)` (routers, middlewares, error handlers, the pages, the container, and the lifespan, which imports the settings of the environment at start).
- `shelfdrop/config.py`: `Settings`.
- `shelfdrop/container.py`: `injectables(settings)`; `open_http` (the `httpx.AsyncClient` of the sources, with the User-Agent of `user_agent`), `new_work_sources` (the metadata clients, in the order of `unavailable`), `new_secret_box`, `new_settings_reader`, `environment_values` (the variables imported once into the settings).
- `shelfdrop/cli/main.py`: the `shelfdrop` command; `shelfdrop db upgrade` applies the migrations, `shelfdrop db check` compares the database with the models (exit 1 on a difference).
- `shelfdrop/db/`: `base.py` (`Base` and its naming convention), `engine.py` (`new_engine`, which sets WAL, the foreign keys and a 5 second wait on every SQLite connection; `open_engine`, `open_session`), `migrate.py` (`upgrade_database`, `check_database`), `models/` (`SourceAnswer`, `CachedWork`, `ReleaseAnswer`, `Tracker`, `FilterRule`, `Setting`, `Secret`, `AuditEntry`), `migrations/` (Alembic, batch mode for SQLite).
- `shelfdrop/works/`:
  - `service.py`: `WorkService` (`search`, `run_search`, `save`, `read_work`), `MetadataClient` (the protocol of a source), `WorkSources`.
  - `repository.py`: `WorkRepository`, the cache (`read_answers`, `save_answers`, `save_works`, `read_work`, `remove_expired`, `commit`).
  - `flights.py`: `SearchFlights` and `SourceHealth`, container singletons.
  - `merge.py`, `ranking.py`, `names.py`: the pure rules of [the work search](how-it-works.md#work-search).
  - `types.py`: `Candidate`, `Name`, `Work`, `NameChoice`, `WorkSearch`, `SearchOptions`, `Clock` and the aliases `Kind`, `Family`, `Form`, `SourceName`.
  - `exceptions.py`: `SourceError`, `QueryTooShortError`, `NoSourceAnsweredError`, `WorkNotFoundError`.
  - `clients/`: `mangaupdates.py`, `kitsu.py`, `myanimelist.py` (the official API, with a Client ID), `anilist.py`, `mangadex.py`, `bnf.py` (SRU, Dublin Core records), `openlibrary.py`, `wikidata.py`, and `http.py` (`get_json`, `post_json`, `get_text`: any failure becomes a `SourceError` named by a status or a class).
- `shelfdrop/releases/`:
  - `service.py`: `ReleaseService` (`start`, `read`, `progress`, `watch`, the trackers, the filters).
  - `jobs.py`: `SearchBoard` (a container singleton: the searches in memory, the queue, the cache), `SearchJob`, `NameQuery`, `ReleaseSource`.
  - `repository.py`: `ReleaseRepository` (the cache of Prowlarr, the trackers, the filter rules, the settings) and `repository_factory` (repositories on sessions of their own, for the searches that outlive their request).
  - `guess.py` (`volumes_of`, `clean_query`, `is_relevant`), `scoring.py` (`compile_rule`, `score_of`, `invalid_rules`), `results.py` (`assemble`, `display_order`), `trackers.py` (`merge_trackers`, `ordered_choices`): pure rules.
  - `types.py`, `exceptions.py`, `clients/prowlarr.py` (`ProwlarrClient`: `search`, `indexers`).
- `shelfdrop/auth/`: the sign-in ([ADR 0013](adr/0013-sign-in-and-sessions.md)): `service.py` (`AuthService`: `sign_in`, `check`, `sign_out`; `JellyfinAddress`, the protocol of the setting it reads), `repository.py` (`SessionRepository`), `throttle.py` (`LoginThrottle`, a container singleton), `types.py` (`Account`, `SignedIn`, `StoredSession`), `exceptions.py`.
- `shelfdrop/clients/`: the clients of the services shared by several domains: `jellyfin.py` (`JellyfinClient`: `authenticate`, `current_user`, `sign_out`, `server_version`, `libraries`), `qbittorrent.py` (`QBittorrentClient`, through the client proxy of qui: `version`, `categories`), `types.py`, `exceptions.py` (`ServiceError`, `ServiceNotConfiguredError`).
- `shelfdrop/settings/`: the settings of the page ([ADR 0012](adr/0012-settings-and-secrets.md)):
  - `service.py`: `SettingsService` (`read`, `save`, `test`, `health`, `read_audit`, `import_environment`).
  - `reader.py`: `SettingsReader` (a container singleton): the settings as the other domains read them at each use, on sessions of their own.
  - `repository.py`: `SettingsRepository` (the settings, the sealed secrets, the audit) and `settings_repository_factory`.
  - `catalog.py`: the keys, kinds, defaults and bounds (`VALUES`, `SECRETS`, `invalid_keys`), pure; `cipher.py`: `SecretBox` (AES-GCM).
  - `probes.py`: `ConnectionProbes` (a container singleton), the tests of the connections, the one file of the settings that calls the clients; `monitor.py`: `ConnectionMonitor` (a container singleton), the tests of the background.
  - `types.py`, `exceptions.py`.
- `shelfdrop/http/`: `errors/` (`ErrorCode`, `ApiError`, the factories, the handlers, `ErrorResponse`), `middleware/` (one file per middleware, `origin.py` among them), `dependencies.py` (`release_session`, `require_session`, `SESSION_COOKIE`).
- `shelfdrop/logging/`: `configure_logging`, `JsonFormatter`, `RequestIdFilter`, `request_id_var`.
- `shelfdrop/modules/`: `health/`, `session/` (the sign-in), `settings/` (the settings, the tests of the connections, the audit), `works/` (`router.py`, `schemas.py`, `errors.py`), `searches/`, `trackers/`, `filters/`, `web/` (`web_router`: a file at the top of the build, or `index.html`).
- `web/src/api/`: the calls of the page to the API (`http.ts`: `request`, `ApiError`, `whenSignedOut`: a `401 not_signed_in` brings the page back to the sign-in), `session.ts` (`readSession`, `signIn`, `signOut`: `App` reads the session at load, `LoginPage` signs in), `works.ts` (`searchWorks`), `searches.ts` (`startSearch`, `readSearch`, `followSearch` on the events), `settings.ts` (the trackers, the filters), `useSearches.ts` (`useWorks`, `useReleases`: the states of the Search pages). `web/src/state/searchSettings.ts` holds the trackers and the filters as Settings edits them, and `web/src/state/settings.ts` the other settings of the API (services, sources, search, Discord) and the secrets replaced or cleared, both saved by its button; `settings.ts` of `api/` also tests a connection (`testConnection`) and reads the tests of the background (`readHealth`, the red dot of the sidebar). The tabs Rangement and API et MCP, the search settings the plan does not list (parallel searches, the two switches), and the other pages still read `web/src/mock/` or local values until their step.
- `shelfdrop/utils/`: `text.py` (`normalize`, `words`, `compact`, `script_of`, `is_latin`), `isbn.py` (`parse_isbn`, `isbn13_of`).

## Layers
A router calls its service and maps its domain exceptions to HTTP errors; a service holds the rules and calls its repository and its clients; a repository runs the queries and commits. `tests/unit/test_layers.py` checks the imports: the domain never imports a framework nor the HTTP layer, wireup stays in the composition and the routers, the routers never touch the database, the utilities import the standard library alone.

The two routes of the work search are `async`: the search waits on every source at once on the event loop, and its service runs the repository in the threadpool ([ADR 0007](adr/0007-work-search.md)).

## Database
Caches: `source_answers` (the candidates a source gave for a family and a normalized text, a day), `cached_works` (a merged work by its id, a week) and `release_answers` (what Prowlarr gave for a name, its categories and its indexers, 10 minutes). Settings: `trackers` (the indexers of Prowlarr, their choices and their order), `filter_rules` (in their order) and `settings` (a JSON value by key: `filters.minimum`, the settings of the page; who changed it last). `secrets` holds the sealed secrets of the services, `audit` who changed which setting and when, never a value ([ADR 0012](adr/0012-settings-and-secrets.md)). `sessions` holds the sessions of the accounts signed in, by the SHA-256 of their token ([ADR 0013](adr/0013-sign-in-and-sessions.md)). The rows of the caches are JSON written and read by `WorkRepository` through Pydantic `TypeAdapter`s of the types of `shelfdrop.works.types`.

## Tests
- `tests/unit/works/test_service.py`: the 10 recorded searches of `tests/unit/works/cases.py`, replayed from `tests/unit/works/fixtures/` (recorded on 2026-10-21 without a MyAnimeList Client ID, when AniList did not answer: its exchanges replay as failures), and the rules of the service with fake sources (`CountingClient`): the cache, the rest of a failed source, one run for two searches, the refusals.
- `tests/unit/works/support.py`: `RecordingTransport`, `ReplayTransport`, `FakeWorkRepository`, `FixedClock`, `new_service`.
- `tests/unit/works/record.py`: records the fixtures again (`uv run python -m tests.unit.works.record [--missing] [slug ...]`; `--missing` keeps the exchanges recorded and asks only those no fixture holds).
- `tests/unit/releases/`: the rules (`test_guess.py` on titles seen on the trackers of the user, `test_scoring.py`, `test_results.py`, `test_trackers.py`), `test_jobs.py` (the board with a Prowlarr that waits for the test), `test_service.py` and `clients/test_prowlarr.py` through `ProwlarrReplay`, which answers from `tests/unit/releases/fixtures/prowlarr.json` (written in the shape of the API of Prowlarr: no real Prowlarr is asked).
- `tests/unit/settings/`: `test_catalog.py`, `test_cipher.py`, `test_reader.py`, `test_service.py` (the audit, the import of the environment, the values of a test) on `FakeSettingsRepository` and `FakeProbes`, `test_probes.py` (each service on its fake, each state), `test_monitor.py`; `support.py` also holds `FakeSettingsReader`, the reader the tests of the other domains give their services.
- `tests/unit/auth/`: `test_service.py` (the sign-in, the refusals, the check every 5 minutes, the sign-out) on `FakeSessionRepository` and `FakeJellyfin`, `test_throttle.py`. `tests/unit/clients/`: `test_jellyfin.py`, `test_qbittorrent.py`, and `support.py` with `FakeJellyfin` and `FakeQui`, `httpx.MockTransport` handlers in the shape of the APIs of Jellyfin and of qBittorrent behind qui.
- `tests/unit/test_main.py`: the application through `httpx.ASGITransport`, signed in through `app.dependency_overrides[require_session]`; without it, every route of the API answers 401.
- `tests/unit/test_naming.py`, `tests/unit/test_layers.py`, `tests/unit/db/test_migrate.py` (the chain of the revisions and the digest of each), `tests/unit/test_integration_parts.py` (the markers of the integration suite).

## Integration tests
`tests/integration/conftest.py` starts one stack per session, `shelfdrop-test-<random>`, from `docker/compose.yaml` and `docker/compose.test.yaml`: the real image of the API, its loopback port drawn at random, and `fake-sources`, WireMock 3.13.2, which the API reaches on the network `sources`, with no way out. Prowlarr is played by it too (`SHELFDROP_PROWLARR_URL` and `SHELFDROP_PROWLARR_API_KEY`, imported into the settings at start, `tests.integration.support.prowlarr_stubs`, from `tests/unit/releases/fixtures/prowlarr.json`). The API sends every request of the metadata clients there (`SHELFDROP_SOURCES_ORIGIN`, `shelfdrop.works.clients.redirect.RedirectTransport`), its first origin in `X-Original-Origin`; the session loads into WireMock one stub per exchange recorded in `tests/unit/works/fixtures/` (`tests.integration.support.recorded_stubs`), a recorded failure replayed as a reset connection, and a request recorded with no stub gets a `404`. A failed source is not skipped there (`SHELFDROP_SOURCE_REST_SECONDS=0`), so that no test disturbs the next one. Jellyfin is played by it too (`SHELFDROP_JELLYFIN_URL`, `tests.integration.support.jellyfin_stubs`: an administrator and an account that is not one, the server and its libraries under the key of the tests), and qBittorrent behind qui (`qbittorrent_stubs`, under the address the tests type). The fixture `session_token` signs in once per run; `client` sends its cookie and the `Origin` of the pages (httpx keeps no `Secure` cookie over plain HTTP), `anonymous` sends no cookie. `tests/integration/support.py` holds `Stack` (its logs, `exec_api`), `FakeSources` (load stubs, count requests, list the unmatched ones), `compose`, `sign_in` and `signed_in_headers`.

### Parts of the integration suite

| Part | Test files | Code that calls for it |
|---|---|---|
| `security` | `test_errors.py`, `test_health.py`, `test_http_headers.py`, `test_logging.py`, `test_migrations.py` | `shelfdrop/http/`, `shelfdrop/logging/`, `shelfdrop/main.py`, `shelfdrop/config.py`, `shelfdrop/container.py`, `shelfdrop/db/`, `shelfdrop/cli/`, `docker/` |
| `pages` | `test_pages.py` | `shelfdrop/modules/web/`, `web/`, `docker/api.Dockerfile` |
| `releases` | `test_release_search.py`, `test_release_manual.py`, `test_release_jobs.py`, `test_release_trackers.py`, `test_release_filters.py` | `shelfdrop/releases/`, `shelfdrop/modules/searches/`, `shelfdrop/modules/trackers/`, `shelfdrop/modules/filters/`, `tests/unit/releases/fixtures/` |
| `works` | `test_work_search.py`, `test_work_sources.py`, `test_work_names.py` | `shelfdrop/works/`, `shelfdrop/modules/works/`, `tests/unit/works/fixtures/` |
| `settings` | `test_settings.py`, `test_settings_tests.py` | `shelfdrop/settings/`, `shelfdrop/modules/settings/`, `shelfdrop/clients/`, the settings read by `shelfdrop/works/` and `shelfdrop/releases/` |
| `auth` | `test_session.py`, `test_sign_in.py` | `shelfdrop/auth/`, `shelfdrop/clients/jellyfin.py`, `shelfdrop/modules/session/`, `shelfdrop/http/dependencies.py`, `shelfdrop/http/middleware/origin.py` |

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
| `releases_search` | `releases` | the search of a work under its names: categories, cleaning, relevance, once each, volumes, order, a failed Prowlarr (`test_release_search.py`) | `shelfdrop/releases/guess.py`, `results.py`, `clients/prowlarr.py`, `shelfdrop/modules/searches/` |
| `releases_manual` | `releases` | the manual search (`test_release_manual.py`) | `shelfdrop/releases/service.py`, `shelfdrop/modules/searches/` |
| `releases_jobs` | `releases` | the shared searches, the queue, the cache, the events (`test_release_jobs.py`) | `shelfdrop/releases/jobs.py`, `shelfdrop/releases/repository.py`, the events route |
| `releases_trackers` | `releases` | the trackers read from Prowlarr, chosen and ordered (`test_release_trackers.py`) | `shelfdrop/releases/trackers.py`, `shelfdrop/modules/trackers/` |
| `releases_filters` | `releases` | the filter rules, the score, an invalid rule (`test_release_filters.py`) | `shelfdrop/releases/scoring.py`, `shelfdrop/modules/filters/` |
| `settings_store` | `settings` | the settings kept, a secret never given back, the audit, the environment imported once, a change read by the next search without a restart (the Client ID of MyAnimeList, a source off, the names) (`test_settings.py`) | `shelfdrop/settings/service.py`, `reader.py`, `repository.py`, `catalog.py`, `cipher.py`, `shelfdrop/modules/settings/` |
| `settings_tests` | `settings` | the tests of the connections, typed or saved, and those of the background (`test_settings_tests.py`) | `shelfdrop/settings/probes.py`, `monitor.py`, `shelfdrop/clients/` |
| `auth_session` | `auth` | every route without a session, the origin of a write, the sign-out (`test_session.py`) | `shelfdrop/http/dependencies.py`, `shelfdrop/http/middleware/origin.py`, `shelfdrop/main.py` |
| `auth_sign_in` | `auth` | the sign-in, its cookie, the refusals, the credentials never logged, the attempts counted; last of its part (`test_sign_in.py`) | `shelfdrop/auth/`, `shelfdrop/clients/jellyfin.py`, `shelfdrop/modules/session/` |
