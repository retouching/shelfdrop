<h1 align="center">shelfdrop</h1>

<p align="center">
  Find manga, books and audiobooks, download them, and shelve them in Jellyfin under the name of their French edition.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-blue.svg">
  <img alt="Run with Docker" src="https://img.shields.io/badge/run%20with-Docker-2496ED.svg">
</p>

shelfdrop sits next to Prowlarr, qBittorrent and Jellyfin on a media server. Type a title: it finds the work in eight metadata sources, searches its releases in Prowlarr under every name the work is published under, sends the ones you pick to qBittorrent, then renames and files the downloaded volumes in your Jellyfin libraries, with their metadata. A web page drives it all; an API and an MCP server let a script or an assistant do the same.

## Features

- **Work search** across MangaUpdates, Kitsu, MyAnimeList, AniList and MangaDex for manga, and the BnF, Open Library and Wikidata for books: one result per work, with every name it is known by and its cover.
- **Release search** in Prowlarr under each name of the work, scored by your filters, ranked by your trackers, in the categories you choose for each indexer.
- **Downloads** sent to qBittorrent through [qui](https://github.com/autobrr/qui), followed live, sent again when a torrent did not arrive.
- **Automatic placement**: volumes renamed and hard-linked into the right library (manga and comics, books, audiobooks), MP3 tracks merged into one M4B with its chapters and cover, metadata written and locked in Jellyfin.
- **Ranger**: the files shelfdrop could not place alone, linked by hand to a work, a volume or chapters, or ignored; files uploaded from the browser land there too.
- **Jellyfin page**: the series of your libraries, their volumes and missing numbers, each file downloadable and editable, and a forced sync of the metadata.
- **Waiting list**: searches kept and run again until a release shows up.
- **Discord journal** of the sends, downloads and placements, with covers.
- **Accounts**: one internal administrator account, and the administrators of your Jellyfin server.
- **API and MCP server** with access tokens (read, or read and download), documented in OpenAPI with Swagger UI at `/api/docs`.
- **Guided first launch** from the browser: the account, Prowlarr, qBittorrent, Jellyfin, the libraries.
- Pages that work on a phone, settings changed live, logs readable from the settings.

## Requirements

- Docker with Compose.
- Prowlarr, qBittorrent with qui, and Jellyfin, reachable from the shelfdrop containers.
- One folder holding both the torrents of qBittorrent and your book libraries, so that placement can use hard links.

## Quick start

```bash
git clone <repository> shelfdrop && cd shelfdrop
cp .env.example .env && chmod 600 .env
# In .env: SHELFDROP_CONTACT (an address the metadata sources can reach you at),
# SHELFDROP_SECRET_KEY (openssl rand -base64 32), SHELFDROP_MEDIA_DIR (the media folder)
docker compose --env-file .env -f docker/compose.yaml up -d --build --wait
```

Open `http://127.0.0.1:8000`. The first launch walks you through the set-up: create the internal account, connect Prowlarr, qBittorrent and Jellyfin, then pick the libraries. Put a reverse proxy with TLS in front of it before exposing it: [installation](docs/installation.md) lists what shelfdrop expects from it.

## Documentation

| Page | What it covers |
| --- | --- |
| [Installation](docs/installation.md) | Docker, the placement worker, permissions, the database, the reverse proxy, upgrades |
| [Configuration](docs/configuration.md) | Every `SHELFDROP_*` variable and the settings of the page |
| [How it works](docs/how-it-works.md) | Work search, release search, downloads, placement, the journal |
| [API](docs/api.md) | Every route, its answers and error codes; the [OpenAPI document](docs/openapi.public.json) |
| [MCP client](docs/mcp-client.md) | Connecting an assistant or a script through the MCP server |
| [Decisions](docs/adr/) | Why shelfdrop is built the way it is |

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers the development set-up, the tests and the commit rules.

## License

[MIT](LICENSE)
