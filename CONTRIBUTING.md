# Contributing

## Set-up

Requirements: [uv](https://docs.astral.sh/uv/), Node.js 24 with pnpm (through `corepack enable`), and Docker for the integration tests.

```bash
uv sync
cp .env.example .env && chmod 600 .env    # set SHELFDROP_CONTACT and SHELFDROP_SECRET_KEY
(cd web && pnpm install)
git config core.hooksPath .githooks        # the checks before each push
```

Run it locally:

```bash
uv run shelfdrop db upgrade
uv run uvicorn --factory shelfdrop.main:create_app --reload   # the API and the pages on 127.0.0.1:8000
(cd web && pnpm dev)                                          # the front-end alone, with live reload
```

## Checks

Every change passes these before it is pushed (the `pre-push` hook runs them):

```bash
uv run ruff format . && uv run ruff check . && uv run mypy
uv run pytest tests/unit
(cd web && pnpm check && pnpm exec vite build)
```

A change of a route or of a schema writes the OpenAPI documents again: `uv run python -m shelfdrop.openapi`, then commit `docs/openapi.json` and `docs/openapi.public.json`.

## Integration tests

`uv run pytest tests/integration -m "<block>"` builds the image, starts an isolated stack (the API, the placement worker, a fake qBittorrent, a real Deluge and a real Transmission, and recorded metadata sources, with no way out to the internet), sends real requests, then removes it. Run the blocks your change touches, one at a time; the blocks and what calls for each are listed in [docs/agents/development.md](docs/agents/development.md#parts-of-the-integration-suite).

## Screenshots

The screenshots of the README (`docs/screenshots/`) are taken by `scripts/screenshots.cjs` with Playwright, from a running shelfdrop, in the official Playwright image. Put the address and an account of that shelfdrop in a file outside the repository (`SHELFDROP_SHOTS_URL`, `SHELFDROP_SHOTS_USERNAME`, `SHELFDROP_SHOTS_PASSWORD`, one `KEY=value` per line, `chmod 600`), then, from the repository root:

```bash
docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp --env-file ~/shots.env \
  -v "$PWD:$PWD" -w "$PWD" mcr.microsoft.com/playwright:v1.56.0-noble \
  sh -c 'npm install --prefix /tmp/shots --no-save --silent playwright@1.56.0 && NODE_PATH=/tmp/shots/node_modules node scripts/screenshots.cjs'
```

It writes ten pages at 1920x1080 and two at 390x844 (twice the density) in WebP. It only reads: it signs in, opens the pages, searches a title (`SHELFDROP_SHOTS_QUERY`, RuriDragon by default), shows the releases of the work of an author (`SHELFDROP_SHOTS_AUTHOR`, Shind, for Masaoki Shindō), searches a title with several works for their shot (`SHELFDROP_SHOTS_WORKS_QUERY`, Call of the Night) and another on the phone (`SHELFDROP_SHOTS_PHONE_QUERY`, Monster) and opens a series (`SHELFDROP_SHOTS_SERIES`, Kaguya-sama by default); any other write of the pages is aborted in the browser. The addresses of the services are replaced by neutral ones before their shot; read every image before committing it, the rest of the data is that of the target.

## Code and commits

- The rules of the code (layers, naming, errors, logging, tests) are in [CLAUDE.md](CLAUDE.md); they hold for humans and coding agents alike.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/), in English, on `master` ([ADR 0002](docs/adr/0002-english-conventional-commits-master.md)).
- The documentation changes in the same commit as the code it describes. Every text the interface shows exists in French, in `web/src/texts.ts`, and in English, in `web/src/i18n/en.ts` (ADR 0008).

## Documents for agents

`docs/agents/` holds the pages written for coding agents: the module map and the layers (`development.md`), the rules of the visible texts (`writing.md`) and the verified behaviours of the sources and tools (`verified-facts.md`). They are useful to a human contributor too, but are not needed to install or use shelfdrop.
