<h1 align="center">shelfdrop</h1>

<p align="center">
  Find manga, books and audiobooks, download them, and shelve them in Jellyfin under the name you choose.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-blue.svg">
  <img alt="Run with Docker" src="https://img.shields.io/badge/run%20with-Docker-2496ED.svg">
</p>

shelfdrop sits next to Prowlarr, a torrent client and Jellyfin on a media server. Type a title: it finds the work in eight metadata sources, searches its releases in Prowlarr under every name the work is published under, sends the ones you pick to the torrent client, then renames and files the downloaded volumes in your Jellyfin libraries, with their metadata, under the name you pick among those the sources know (in the order of languages you set, French first by default) or one of your own. A web page drives it all; an API and an MCP server let a script or an assistant do the same.

## Screenshots

<p align="center">
  <a href="docs/screenshots/search-releases.webp"><img src="docs/screenshots/search-releases.webp" alt="The releases of a work, searched under each of its names, scored and ranked"></a>
  <br><sub>The releases of a work, searched in Prowlarr under each of its names, scored and ranked.</sub>
</p>

<table>
  <tr>
    <td width="50%"><a href="docs/screenshots/search-works.webp"><img src="docs/screenshots/search-works.webp" alt="Work search: one result per work, from every source, with its names"></a><br><sub>Work search: one result per work, from every source, with its names</sub></td>
    <td width="50%"><a href="docs/screenshots/downloads.webp"><img src="docs/screenshots/downloads.webp" alt="Downloads, followed live, and where each was shelved"></a><br><sub>Downloads, followed live, and where each was shelved</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/jellyfin-series.webp"><img src="docs/screenshots/jellyfin-series.webp" alt="Jellyfin page: the series of the libraries"></a><br><sub>Jellyfin page: the series of the libraries</sub></td>
    <td width="50%"><a href="docs/screenshots/jellyfin-series-dialog.webp"><img src="docs/screenshots/jellyfin-series-dialog.webp" alt="A series: its work (to change, or to adopt its files), and the titles, covers and summaries the sources propose"></a><br><sub>A series: its work (to change, or to adopt its files), and the titles, covers and summaries the sources propose</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/place.webp"><img src="docs/screenshots/place.webp" alt="Place: the files to match by hand, and every file of the library"></a><br><sub>Place: the files to match by hand, and every file of the library</sub></td>
    <td width="50%"><a href="docs/screenshots/waiting-list.webp"><img src="docs/screenshots/waiting-list.webp" alt="Waiting list: searches run again until a release shows up"></a><br><sub>Waiting list: searches run again until a release shows up</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/settings-services.webp"><img src="docs/screenshots/settings-services.webp" alt="Settings: Prowlarr, the torrent client (qBittorrent, qui, Deluge, Transmission), Jellyfin"></a><br><sub>Settings: Prowlarr, the torrent client (qBittorrent, qui, Deluge, Transmission), Jellyfin</sub></td>
    <td width="50%"><a href="docs/screenshots/settings-logs.webp"><img src="docs/screenshots/settings-logs.webp" alt="Settings: the logs of the API and of the placement worker"></a><br><sub>Settings: the logs of the API and of the placement worker</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/sign-in.webp"><img src="docs/screenshots/sign-in.webp" alt="Sign-in: the internal account or a Jellyfin administrator"></a><br><sub>Sign-in: the internal account or a Jellyfin administrator</sub></td>
    <td width="50%"></td>
  </tr>
</table>

On a phone:

<p align="center">
  <a href="docs/screenshots/mobile-search-menu.webp"><img src="docs/screenshots/mobile-search-menu.webp" alt="The menu over the work search, on a phone" width="260"></a>
  &nbsp;
  <a href="docs/screenshots/mobile-downloads.webp"><img src="docs/screenshots/mobile-downloads.webp" alt="The downloads as cards, on a phone" width="260"></a>
</p>

How to take them again: [CONTRIBUTING.md](CONTRIBUTING.md#screenshots).

## Features

- **Work search** across MangaUpdates, Kitsu, MyAnimeList, AniList and MangaDex for manga, and the BnF, Open Library and Wikidata for books: one result per work, with every name it is known by and its cover.
- **Title proposals**: every field where a title is chosen (the name on the shelf, the title of a series) proposes the names the sources know, each with its language and its source, in the orders of languages and sources you set; a title of your own is always possible.
- **Release search** in Prowlarr under each name of the work, scored by your filters, ranked by your trackers, in the categories you choose for each indexer.
- **Downloads** sent to qBittorrent (directly or through [qui](https://github.com/autobrr/qui)), Deluge or Transmission, into a folder of your choice for each kind, followed live, sent again when a torrent did not arrive.
- **Automatic placement**: volumes renamed and put into the right library (manga and comics, books, audiobooks), as hard links (the default), hard links or else copies, or copies always, never over an existing file; MP3 tracks merged into one M4B with its chapters and cover, metadata written and locked in Jellyfin.
- **Place**: the files shelfdrop could not place alone, linked by hand to a work, a volume or chapters, or ignored; files uploaded from the browser land there too.
- **Jellyfin page**: the series of your libraries, their volumes and missing numbers, each file downloadable and editable, and a forced sync of the metadata. A series matched to the wrong work is linked to another; the files you added by hand are adopted, numbered from Jellyfin or their names, and renamed to the names of the shelf if you ask.
- **Waiting list**: searches kept and run again until a release shows up.
- **Discord journal** of the sends, downloads and placements, with covers, in French or in English (a setting).
- **Accounts**: one internal administrator account, and the administrators of your Jellyfin server.
- **API and MCP server** with access tokens (read, or read and download), documented in OpenAPI with Swagger UI at `/api/docs`; the seven MCP tools let an assistant search, send, follow and place.
- **Guided first launch** from the browser: the account, Prowlarr, the torrent client, Jellyfin, the libraries.
- Pages in English and in French, the language chosen on each device (the browser's by default); addresses you can bookmark and share (a search, a work, a series, the filters of Place), Back and Forward included; pages that work on a phone, settings changed live, logs readable from the settings.

## Requirements

- Docker with Compose.
- Prowlarr, a torrent client and Jellyfin, reachable from the shelfdrop containers. The torrent client: qBittorrent, directly or through qui; Deluge 2 with its plugin Label enabled; or Transmission 3.00 or later ([installation](docs/installation.md#the-torrent-client)).
- The torrent client and shelfdrop seeing the downloads at the same path. With the default placement mode (hard links), the downloads and your book libraries in one folder, on one file system; the copy modes lift that, each file then taking its space twice ([installation](docs/installation.md#the-placement-worker)).

## Quick start

```bash
git clone <repository> shelfdrop && cd shelfdrop
cp .env.example .env && chmod 600 .env
# In .env: SHELFDROP_CONTACT (an address the metadata sources can reach you at),
# SHELFDROP_SECRET_KEY (openssl rand -base64 32), SHELFDROP_MEDIA_DIR (the media folder)
docker compose --env-file .env -f docker/compose.yaml up -d --build --wait
```

Open `http://127.0.0.1:8000`. The first launch walks you through the set-up: create the internal account, connect Prowlarr, the torrent client and Jellyfin, then pick the libraries. Put a reverse proxy with TLS in front of it before exposing it: [installation](docs/installation.md) lists what shelfdrop expects from it.

## Documentation

| Page | What it covers |
| --- | --- |
| [Installation](docs/installation.md) | Docker, the torrent client, the placement worker, permissions, the database, the reverse proxy, upgrades |
| [Configuration](docs/configuration.md) | Every `SHELFDROP_*` variable and the settings of the page |
| [How it works](docs/how-it-works.md) | Work search, release search, downloads, placement, the journal |
| [API](docs/api.md) | Every route, its answers and error codes; the [OpenAPI document](docs/openapi.public.json) |
| [MCP client](docs/mcp-client.md) | Connecting an assistant or a script through the MCP server |
| [Decisions](docs/adr/) | Why shelfdrop is built the way it is |

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers the development set-up, the tests and the commit rules.

## License

[MIT](LICENSE)
