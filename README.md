<h1 align="center">shelfdrop</h1>

shelfdrop finds manga, books and audiobooks, downloads them and shelves them into the Jellyfin library under the name of their French edition. It runs on the media server, behind a reverse proxy, and only the administrators of the Jellyfin server use it.

- **Work search**: a title, in any language, gives the work and every name it is published under, merged from eight metadata sources: MangaUpdates, Kitsu, MyAnimeList (with a Client ID), AniList and MangaDex for manga, the BnF, Open Library and Wikidata for books ([how it works](docs/how-it-works.md#work-search)).
- **Front-end**: the pages of shelfdrop (`web/`), served by the API.

## Quick start
Docker, or uv and pnpm, are required.

```bash
cp .env.example .env    # then set SHELFDROP_CONTACT
docker compose --env-file .env -f docker/compose.yaml up -d --build --wait
curl -s 'http://127.0.0.1:8000/api/v1/works?q=Chainsaw%20Man&kind=manga'
```

Without Docker: `uv sync`, `uv run shelfdrop db upgrade`, `uv run uvicorn --factory shelfdrop.main:create_app`.

## Documentation
- [Installation](docs/installation.md): the image, the database, the reverse proxy, the upgrades.
- [Configuration](docs/configuration.md): every `SHELFDROP_*` variable.
- [API](docs/api.md): the routes, their answers and the error codes.
- [How it works](docs/how-it-works.md): a request, a work search, the cache.
- [Development](docs/development.md): the module map, the layers, the tests.
- [Visible texts](docs/writing.md): the rules of every text the interface shows.
- [Decisions](docs/adr/) and [verified facts](docs/verified-facts.md).
- `CLAUDE.md`: the rules of the code, for developers and coding agents.
