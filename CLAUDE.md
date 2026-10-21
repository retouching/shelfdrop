# shelfdrop

Finds, downloads and shelves manga, books and audiobooks into Jellyfin. Today: the search of a work in the metadata sources, the search of its releases in Prowlarr with the trackers and the filters, the sign-in and the settings, the downloads sent to qBittorrent and their follow-up, their HTTP routes, and the front-end (`web/`), served by the API.

## Stack
- Python 3.13 (`requires-python = ">=3.13"`), dependencies managed by uv; `uv.lock` is committed. Flat layout (`[tool.uv.build-backend] module-root = ""`).
- FastAPI + uvicorn; configuration via pydantic-settings; dependency injection with wireup (ADR 0004); httpx asks the metadata sources, defusedxml reads the records of the BnF.
- SQLAlchemy 2 (synchronous) on SQLite; Alembic migrations (ADR 0005).
- ruff (lint + format), mypy (strict + pydantic plugin), pytest 9 (strict mode, warnings are errors).
- The front-end: React, Vite, Tailwind, TypeScript strict, ESLint and Prettier, built by pnpm (ADR 0008).

## Repository map
Details per file and symbol: [docs/development.md](docs/development.md#module-map).
- `shelfdrop/main.py`: `create_app()` and `build_app()`, the HTTP composition root; the only place that registers routers and middlewares and calls wireup `setup()`.
- `shelfdrop/config.py`: `Settings`, the only place that reads configuration (`SHELFDROP_*` env vars, optional `.env`).
- `shelfdrop/container.py`: `injectables(settings)`, the one list of wireup registrations, and the HTTP client and the metadata clients it builds.
- `shelfdrop/db/`: engine and sessions, ORM models (registry `shelfdrop/db/models/__init__.py`), Alembic migrations.
- `shelfdrop/works/`: the work search: `service.py` (`WorkService`), `repository.py` (the cache), `flights.py` (the searches running and the sources at rest, shared by the requests), the pure rules `merge.py`, `ranking.py` and `names.py`, `types.py`, `exceptions.py`, and `clients/`, one module per metadata source plus `http.py`, their requests.
- `shelfdrop/releases/`: the release search in Prowlarr: `service.py` (`ReleaseService`), `jobs.py` (`SearchBoard`: the searches in memory, shared, queued, cached), `repository.py`, the pure rules `guess.py`, `scoring.py`, `results.py`, `trackers.py`, `types.py`, `exceptions.py`, and `clients/prowlarr.py`.
- `shelfdrop/downloads/`: the releases sent to qBittorrent and their follow-up ([ADR 0014](docs/adr/0014-downloads.md)): `service.py` (`DownloadService`), `sender.py` (`DownloadSender`: the sends after their request), `repository.py`, the pure `states.py`, `types.py`, `exceptions.py`.
- `shelfdrop/journal/`: the events posted on Discord ([ADR 0015](docs/adr/0015-journal.md)): `service.py` (`Journal`, `JournalSender`), `embeds.py`, `texts.py` (the French texts of the messages), `repository.py`, `types.py`.
- `shelfdrop/auth/`: the sign-in with an administrator of Jellyfin and the sessions ([ADR 0013](docs/adr/0013-sign-in-and-sessions.md)): `service.py` (`AuthService`), `repository.py`, `throttle.py`, `types.py`, `exceptions.py`. `shelfdrop/clients/`: the clients of the services several domains share (`jellyfin.py`, `qbittorrent.py`, `discord.py`).
- `shelfdrop/settings/`: the settings of the page ([ADR 0012](docs/adr/0012-settings-and-secrets.md)): `service.py` (`SettingsService`), `reader.py` (`SettingsReader`: the settings the other domains read at each use), `repository.py`, the pure `catalog.py`, `cipher.py` (`SecretBox`), `probes.py` (the tests of the connections), `monitor.py` (the tests of the background), `types.py`, `exceptions.py`.
- `shelfdrop/http/`: global HTTP layer: errors, middlewares, `release_session`; `shelfdrop/logging/`: logging shared by the API and the CLI; `shelfdrop/utils/`: generic pure helpers.
- `shelfdrop/modules/<feature>/`: one package per HTTP feature (`health`, `session`, `settings`, `works`, `searches`, `releases`, `downloads`, `trackers`, `filters`, `web`: the pages of the front-end).
- `shelfdrop/cli/`: the `shelfdrop` command (`shelfdrop db upgrade`, `shelfdrop db check`).
- `web/`: the front-end; its visible texts are in `web/src/texts.ts` and follow [docs/writing.md](docs/writing.md).
- `tests/unit/`, `tests/integration/`: see Testing rules. `docker/`: `api.Dockerfile`, `compose.yaml` (the stack) and `compose.test.yaml` (the test stack, over it). `.githooks/pre-push`: the gates before each push.
- `docs/`: the pages, the ADRs and the verified facts (see Documentation); `README.md`: what shelfdrop is and where each page is.

## Structure rules
- HTTP features live in `shelfdrop/modules/<feature>/`. Everything else (CLI, configuration, database, domains, global HTTP layer, utilities) is a module or a package directly under `shelfdrop/`, never under `modules/`.
- A concern stays a single module while it holds one kind of content (`shelfdrop/config.py`); it becomes a package as soon as it holds several kinds (`shelfdrop/works/`).
- One file = one kind of content:
  - `router.py` (`APIRouter(route_class=WireupRoute)` and thin endpoints: call a service received as `Injected[...]`, turn its domain exceptions into the errors of `errors.py`, return a schema; no `Session`, no commit, no rule, no SQL), `schemas.py` (Pydantic request/response models only), `errors.py` (one HTTP error factory per code of the feature).
  - `service.py` (one service class holding the rules; its repository, clients and values come through its constructor; a use case that writes commits last through its repository; never imports FastAPI, wireup nor SQLAlchemy), `repository.py` (one repository class built on the `Session`: the only place for queries and `commit()`).
  - `types.py` (dataclasses, enums and type aliases; no Pydantic HTTP schema, no ORM model), `exceptions.py` (exception classes), `shelfdrop/db/models/<entity>.py` (one ORM model, also added to the registry), `shelfdrop/http/middleware/<name>.py` (one pure ASGI middleware, no `BaseHTTPMiddleware`).
  - Pure rule modules (`merge.py`, `ranking.py`, `names.py`) do no I/O. A `Protocol` stays in the file that consumes it (`MetadataClient` in `shelfdrop/works/service.py`). Helpers and constants used by a single file stay in that file. `__init__.py` files stay empty, except the model registry.
- Utilities: a generic, pure helper goes in `shelfdrop/utils/<topic>.py`: it names no domain of this project, imports only the standard library, raises nothing and writes no message (`normalize`, `parse_isbn`).
- Every Dockerfile (`docker/<image>.Dockerfile`) and Compose file (`docker/compose*.yaml`) lives in `docker/`; the build context is the repository root, with its single `.dockerignore`. Every `docker compose` command runs from the repository root with `--env-file .env -f docker/compose.yaml`.
- Dependencies point one way (`tests/unit/test_layers.py`): `main` → `container`, `modules`, `http`, `logging`, `config`; `modules` → `works`, `releases`, `downloads` (services, types, exceptions), `http`; `container` → `works`, `releases`, `downloads`, `settings`, `db`, `config`; `works`, `releases`, `downloads`, `settings`, `auth` → `db` (their `repository.py` alone), `utils`; `releases`, `downloads`, `settings`, `auth` → `works` (types, names, exceptions); `downloads` → `releases` (types, exceptions), `clients`; `auth` → `settings` (the cipher), `clients`; `downloads`, `auth` → `journal` (types); `journal` → `clients`, `db` (its `repository.py`), `works` (types); `http` → `auth` (`require_session`). `works`, `releases` and `downloads` read their settings and the releases of a search through a `Protocol` of their own, never by an import of `settings` or of another service. `works`, `releases`, `downloads`, `journal`, `settings`, `auth`, `clients`, `db`, `utils` and `logging` never import FastAPI, Starlette, wireup or `shelfdrop.http`; only `container.py`, `main.py`, `http/dependencies.py` and the routers import wireup; only `container.py` and `shelfdrop/works/` import the metadata clients, only `container.py` and `shelfdrop/releases/` the Prowlarr client, only `container.py`, `shelfdrop/auth/`, `shelfdrop/downloads/` and `shelfdrop/journal/` the clients of `shelfdrop/clients/`; `shelfdrop/settings/probes.py` (the tests of the connections) imports every client.
- Never run a package file as a script (`python shelfdrop/...py`): `shelfdrop/http` and `shelfdrop/logging` would shadow the standard library. Use `uv run shelfdrop`, `python -m` or uvicorn `--factory`.

## Commands
Setup: `uv sync`, `cp .env.example .env` (`chmod 600 .env`), then set `SHELFDROP_CONTACT` and `SHELFDROP_SECRET_KEY`; `cd web && pnpm install`.

Quality gates (all must pass before work is done):
- `uv run ruff format .`, `uv run ruff check .` (add `--fix` for safe autofixes), `uv run mypy`, `uv run pytest tests/unit`
- `cd web && pnpm check` (types, ESLint, Prettier) and `pnpm exec vite build`
- The hook `.githooks/pre-push` runs them before each push (enable it once per clone: `git config core.hooksPath .githooks`).
- The hook never runs the integration tests. `uv run pytest tests/integration` (the whole suite: on the request of the user alone, never before a push): builds the image, starts an isolated stack `shelfdrop-test-<random>` (the API and `fake-sources`, a WireMock that replays the recorded exchanges of `tests/unit/works/fixtures/` and plays Prowlarr from `tests/unit/releases/fixtures/prowlarr.json`, on a network with no way out), sends real HTTP requests, runs commands in the container, then `down --volumes`. Requires Docker; it fails (never skips) without it.
- `uv run pytest tests/integration -m "<block>"`: the blocks of the integration suite, run once each, at the end of a big point: the blocks whose code the change touched and the block of every integration test it changed, one block per command, one after another; a whole part (`-m "<part>"`) only when every one of its blocks is called for. The path is always `tests/integration`, never a list of files. The parts, their blocks and the code that calls for each: [docs/development.md](docs/development.md#parts-of-the-integration-suite).
- Every run of the integration suite by an agent is verbose and goes to a file outside the repository, whose path is given to the user when the run starts: `uv run pytest tests/integration -m "<block>" -v -p no:cacheprovider > <file>.log 2>&1`. After the fix of a failed test, run that test by its id, not its part again.
- `uv run python -m tests.unit.works.record [slug ...]`: records the fixtures of the work search again from the real sources (network); only when a source changed its answers, and the diff of the fixtures is read before the commit. With `--missing`, only the requests no fixture holds are sent (a change of the search that asks more, or a new case).

Run:
- `uv run shelfdrop db upgrade`, then `uv run uvicorn --factory shelfdrop.main:create_app --reload`: the API on 127.0.0.1:8000, its database in `.data/`.
- `cd web && pnpm dev`: the front-end alone.
- `docker compose --env-file .env -f docker/compose.yaml up -d --build --wait`, `... logs -f api`, `... down` (`--volumes` also wipes the database).

Dependencies: `uv add <pkg>`, `uv add --dev <pkg>`; never `pip install`. Commit `uv.lock` with the change.

## Code conventions
- Everything in English: code, comments, docs, API messages, logs. Every text the front-end shows is French and follows [docs/writing.md](docs/writing.md), and lives in `web/src/texts.ts` alone.
- Type everything; mypy and TypeScript run in strict mode. No `# type: ignore`, `# noqa` or ESLint disable without an explanation on the same line.
- No name starts with an underscore (`tests/unit/test_naming.py`), but `_` alone, dunders and what a library imposes (`Settings(_env_file=None)`).
- Read configuration only through `Settings`, never `os.environ`. `Settings` holds the bootstrap alone (what the process needs before its database); a setting the page changes goes in `shelfdrop/settings/catalog.py` and is read at each use (ADR 0012). A new variable gets a `SHELFDROP_` name, an entry in `.env.example` and, if the container needs it, in `docker/compose.yaml`.
- Endpoints are sync `def` (SQLAlchemy is synchronous), but the routes of the work search, `async` because a search waits on every source at once, those of the release search (`searches`, `releases`, `trackers`, `filters`), `async` because a search runs on the event loop and streams its progress, and their service holds the async client of Prowlarr, and those of the downloads, `async` because their service holds the async clients of qBittorrent and the sender; their service runs the repository in the threadpool (`anyio.to_thread`) and `release_session` closes the session there after the response (ADR 0007).
- Raise an `ApiError` for every HTTP error, built by the factories of `shelfdrop/http/errors/errors.py` alone, through the `errors.py` of the feature. Every error body is `{"code", "detail", "data"}` ([contract](docs/api.md#errors)). `ErrorCode` (`shelfdrop/http/errors/types.py`) is the single list of codes, each member commented with its status, meaning and `data`. `422` bodies never echo input values.
- No `print` in `shelfdrop/`; log with `logging.getLogger(__name__)`, configured by `configure_logging()` alone. Expected failures log the exception class only; never log `Settings`, URLs, headers, bodies or query strings: the address of a source may carry a key.
- Every route but `/health` and the pages is served under `Settings.api_prefix` (`/api`), applied by `build_app()` alone; every router prefix starts with its version (`/v1/works`). Every route of the API needs a session (`require_session`, put by `build_app()` on every router but the one of the session); a write needs the `Origin` of its host (ADR 0013). Client IP = `request.client.host` as resolved by uvicorn (`FORWARDED_ALLOW_IPS` set to the proxy).
- Response headers come only from the middlewares in `shelfdrop/http/middleware/`; uvicorn runs with `--no-server-header`.

## Testing rules
- Unit tests (`tests/unit/`) need no Docker, network or database. They mirror the packages, with an `__init__.py` in every folder: `shelfdrop/<package>/<module>.py` → `tests/unit/<package>/test_<module>.py`, `shelfdrop/<module>.py` → `tests/unit/test_<module>.py`.
- Services are tested with fakes that subclass the real repositories with `@typing.override`, built on `tests.unit.support.no_session()` (`FakeWorkRepository` records its commits). The metadata clients are tested through the recorded exchanges of `tests/unit/works/fixtures/` (`ReplayTransport`) or an `httpx.MockTransport`; no unit test opens a connection.
- What a recorded search must find comes from the decisions of the user (the name on the shelf, the names searched, `tests/unit/works/cases.py`), never from what the code happens to return: when they disagree, the disagreement is reported, the case is not bent.
- In-process HTTP goes through `httpx.ASGITransport` on `build_app()`, never `TestClient`. Tests that call `create_app()`, the CLI `main()` or `configure_logging()` use the `isolated_logging` fixture and read logs from `capsys`.
- Integration tests (`tests/integration/`) talk to the real image over HTTP, run commands in its container (`stack.exec_api`) and read its logs (`stack.log_records(request_id, expected=n)`, filtered on a unique `X-Request-ID`, read again without sleeping); never a call of the application code in-process, never a mock of the database. The sources, Prowlarr and Jellyfin are played by `fake-sources` alone (`SHELFDROP_SOURCES_ORIGIN`, a setting of the test stack, and `SHELFDROP_PROWLARR_URL`, `SHELFDROP_JELLYFIN_URL`, imported into the settings at start); a test signs in through the fixtures `session_token`, `client` (signed in) or `anonymous`, never twice more than it needs: the sign-ins are counted; a test that needs another answer loads its own stub, on a text of its own. What they check comes from the agreed contract (the plan, the decisions of the user, `tests/unit/works/cases.py`), never from what the code happens to do.
- Every file of `tests/integration/` carries the marker of its part, and, in a part of several files, the marker of its block (`pytestmark = [pytest.mark.<part>, pytest.mark.<block>]`); a new file joins a part and a block of the tables or brings new ones: its markers in `pyproject.toml`, its lines in `tests/unit/test_integration_parts.py` and in [docs/development.md](docs/development.md#parts-of-the-integration-suite).
- The settings reserved for the test stack (`TEST_STACK_SETTINGS` of `shelfdrop/config.py`) are set by `docker/compose.test.yaml` alone, never in `.env.example`, `docker/compose.yaml` nor a `.env` file.
- Tests are independent: each builds its own data. No `sleep` but the delays of a fake source. Warnings are errors; a `filterwarnings` ignore is acceptable only for a third-party warning, scoped, with a comment.

## Database and migrations
- Schema changes go through Alembic only. A change edits the models in `shelfdrop/db/models/` (and the registry), then adds one revision generated on a database at head (`SHELFDROP_DATA_DIR=<empty dir> uv run alembic upgrade head`, then `uv run alembic revision --autogenerate -m "<what changes>"`), reviewed, formatted, with its sha256 added to `DIGESTS` of `tests/unit/db/test_migrate.py` in the same commit.
- A pushed revision is never edited, renamed nor deleted: a mistake is fixed by a new revision. A revision carries the existing rows itself, in SQL, and imports no model.
- Migrations apply when the container starts (`shelfdrop db upgrade`); `shelfdrop db check` reports no difference between the database at head and the models (`tests/integration/test_migrations.py`). Revision files are excluded from mypy.

## Docker hygiene
- This project owns only the image `shelfdrop-api:local`, the Compose project `docker` of `docker/compose.yaml` and its volume, the test projects `shelfdrop-test-*` (their stacks and volumes), and the containers an agent starts for a check (named `shelfdrop-check-*`), which it removes as soon as the check ends.
- Leftover test stacks (after killing pytest): `docker compose ls --all --filter name=shelfdrop-test`, then `docker compose -p <name> -f docker/compose.yaml -f docker/compose.test.yaml down --volumes --remove-orphans`; an agent removes only the stacks it started and reports the others.
- Never run `docker system prune`, `docker image prune -a` or `docker volume prune`, never `docker compose config` without `--quiet`, and never remove what this project did not create.

## Git
- Default branch `master`. Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `build:`, `chore:`), in English, small focused commits, each passing the gates; authored by the owner of the repository alone: no `Co-authored-by`, no `Signed-off-by`, no mention of a tool.
- The version of `pyproject.toml` (`X.Y.Z` from `0.1.0`) rises in the last commit of a push that changes the code since the last tag: the patch for fixes alone, the minor otherwise.
- Never commit `.env`, tokens, secrets, `CLAUDE.local.md` or caches.

## Documentation
- Reference documents, in English but `docs/writing.md`, whose examples are French. Every agent and developer reads them before analysing, planning, coding or reviewing; when the code contradicts them, the code wins: fix the docs in the same change, or report the bug.
  - `README.md`; the pages of `docs/`: `installation.md`, `configuration.md`, `api.md`, `how-it-works.md` (for the operator), `development.md` (module map, layers, database, tests), `writing.md` (the visible texts); `docs/adr/NNNN-<slug>.md` (one living ADR per subject); `docs/verified-facts.md` (behaviours of the sources and libraries this code relies on, each with its evidence, its pinning test and its re-verification trigger).
- A rule or a command lives here; a description or a contract lives in `docs/`; code-level detail in docstrings and `ErrorCode` comments. Each description has one home: link to it, never copy it.
- The docs change with the code, in the same commit: what a change adds is described, what it modifies is updated, what it removes is deleted, every reference included.
- An ADR is `# NNNN. Subject`, then `Status: Accepted`, `Date:` (last change of the decision) lines, then `## Context` (who decided, why), `## Decision`, `## Rejected alternatives`, `## Consequences` and, when something no longer holds, `## Replaced`. It states only what the code implements; a decision no code implements yet waits outside the repository, with the plan of its feature, and enters its ADR in the commit that implements it. ADR numbers and fact IDs are never reused.
- Cite code by repository path or qualified symbol and tests as `path::test_name`, never by line number; never cite agent artifacts (plans, analyses kept outside the repository).

## Definition of done
1. `uv run ruff format .`, `uv run ruff check .` and `uv run mypy` are clean; `pnpm check` is clean when `web/` changed.
2. `uv run pytest tests/unit` passes; the blocks of the integration suite the change calls for pass, each run once, at its end; the whole `uv run pytest` runs on the request of the user alone.
3. New behaviour is covered by tests at the right level (see Testing rules).
4. The docs follow the change in the same commit (see Documentation); `.env.example` follows the variables.
5. No container, image or volume of a check is left; other leftovers are reported, never removed.
