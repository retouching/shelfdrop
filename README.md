<h1 align="center">shelfdrop</h1>

shelfdrop finds manga, books and audiobooks, downloads them and shelves them into the Jellyfin library under the name of their French edition. It runs on the media server, behind a reverse proxy, and only its internal account and the administrators of the Jellyfin server use it.

- **Work search**: a title, in any language, gives the work and every name it is published under, merged from eight metadata sources: MangaUpdates, Kitsu, MyAnimeList (with a Client ID), AniList and MangaDex for manga, the BnF, Open Library and Wikidata for books ([how it works](docs/how-it-works.md#work-search)).
- **Release search**: the releases of a work in Prowlarr, under each of its names, scored by the filters and ranked by the trackers ([how it works](docs/how-it-works.md#release-search)).
- **Downloads**: the releases chosen sent to qBittorrent (through qui), each found there by its hash, then followed live; a torrent not received is sent again ([how it works](docs/how-it-works.md#downloads)).
- **Sign-in**: the internal account of shelfdrop, or the administrators of the Jellyfin server with their account of Jellyfin ([ADR 0013](docs/adr/0013-sign-in-and-sessions.md)).
- **First launch**: a set-up from the pages: the internal account, then Prowlarr, qBittorrent, Jellyfin, the libraries and the folder of the uploads, before the rest of the site opens ([ADR 0024](docs/adr/0024-first-launch-setup.md)).
- **API and MCP**: access tokens (reading, or reading and downloading) for the API and for an MCP server at `/mcp`, whose tools search, send, follow and place as the page does; the API documented in OpenAPI ([ADR 0020](docs/adr/0020-access-tokens.md), [ADR 0022](docs/adr/0022-mcp-server.md), [an MCP client](docs/mcp-client.md)).
- **Settings**: the services, their keys (sealed), the sources and the search, changed from the page without a restart, each connection tested ([ADR 0012](docs/adr/0012-settings-and-secrets.md)); the logs of the API and of the placement worker, read from the page ([ADR 0023](docs/adr/0023-logs.md)).
- **Front-end**: the pages of shelfdrop (`web/`), served by the API.

## Quick start
Docker, or uv and pnpm, are required.

```bash
cp .env.example .env    # then set SHELFDROP_CONTACT, SHELFDROP_SECRET_KEY
chmod 600 .env
docker compose --env-file .env -f docker/compose.yaml up -d --build --wait
```

Then open `http://127.0.0.1:8000`: the first launch goes through the set-up ([installation](docs/installation.md#the-first-launch)); afterwards, sign in with the internal account or an administrator account of Jellyfin.

Without Docker: `uv sync`, `uv run shelfdrop db upgrade`, `uv run uvicorn --factory shelfdrop.main:create_app`.

## Documentation
- [Installation](docs/installation.md): Docker, the placement worker, the database, what the reverse proxy must pass, the upgrades.
- [Configuration](docs/configuration.md): every `SHELFDROP_*` variable.
- [API](docs/api.md): the routes, their answers and the error codes, the access tokens, the MCP server; [OpenAPI](docs/openapi.public.json).
- [An MCP client](docs/mcp-client.md): the token, the entry of a client, the tools of the MCP server.
- [How it works](docs/how-it-works.md): a request, a work search, the cache.
- [Development](docs/development.md): the module map, the layers, the tests.
- [Visible texts](docs/writing.md): the rules of every text the interface shows.
- [Decisions](docs/adr/) and [verified facts](docs/verified-facts.md).
- `CLAUDE.md`: the rules of the code, for developers and coding agents.
