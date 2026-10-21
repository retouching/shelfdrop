# Configuration

`shelfdrop.config.Settings` reads every setting from the environment (`SHELFDROP_*`) and from a `.env` file in the working directory, when there is one. An invalid value stops the process at start.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SHELFDROP_CONTACT` | required | An address where the operator can be reached, written in the User-Agent of every request to a metadata source, as their usage policies ask. |
| `SHELFDROP_SECRET_KEY` | required by the API | The key the secrets of the database are sealed with: 32 characters at least (`openssl rand -base64 32`), in a `.env` file of mode 600. Losing it loses the secrets. Never logged nor shown. |
| `SHELFDROP_DATA_DIR` | `.data` (`/data/shelfdrop` in the image) | The directory of the database, created at start. |
| `SHELFDROP_STATIC_DIR` | `shelfdrop/static` (`/app/static` in the image) | The built front-end. Without an `index.html` there, no page is served. |
| `SHELFDROP_API_PREFIX` | `/api` | The prefix of every route but `/health` and the pages: one or more `/segment`. |
| `SHELFDROP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. SQLAlchemy, httpx and httpcore never log below `WARNING`. |
| `SHELFDROP_LOG_FORMAT` | `json` | `json` (one object per line) or `text`. |
| `SHELFDROP_PUBLIC_URL` | none | The address of the pages as the browser reaches them (`https://shelfdrop.maigo.party`): the title of each message of the journal links there. |

Imported once into the database, at the first start where they are set ([ADR 0012](adr/0012-settings-and-secrets.md)); then the settings page holds them, and a later change of the variable is ignored:

| Variable | Setting |
| --- | --- |
| `SHELFDROP_PROWLARR_URL` | `prowlarr.url`, the address of Prowlarr (`http://prowlarr:9696`) |
| `SHELFDROP_PROWLARR_API_KEY` | the secret `prowlarr.api_key` |
| `SHELFDROP_JELLYFIN_URL` | `jellyfin.url`, the address of Jellyfin (`http://jellyfin:8096`) |
| `SHELFDROP_MYANIMELIST_CLIENT_ID` | the secret `sources.myanimelist.client_id`, the Client ID of the MyAnimeList API (myanimelist.net/apiconfig) |
| `SHELFDROP_DISCORD_WEBHOOK` | the secret `discord.webhook`, the webhook of Discord the journal posts on |

## Settings of the page
Kept in the database (`settings`, `secrets`), read at each use, so a change applies without a restart. `shelfdrop.settings.catalog` lists them:

| Key | Default | Meaning |
| --- | --- | --- |
| `prowlarr.url`, `qbittorrent.url`, `jellyfin.url` | none | The address of each service; for qBittorrent, the address of qui (`http://qui:7476`), whose client proxy key is `qbittorrent.api_key`. Without the address or the key of Prowlarr, no release is searched (`prowlarr_unavailable`); without those of qui, a download is not received. The downloads go to the categories of qBittorrent `manga`, `ebook`, `audiobook` (by kind) and `shelfdrop-manual` (the manual ones), which its test looks for. |
| `sources.<source>.enabled` | on | Whether a metadata source is asked (`mangaupdates`, `kitsu`, `myanimelist`, `anilist`, `mangadex`, `bnf`, `openlibrary`, `wikidata`). MyAnimeList is asked with its Client ID alone. |
| `search.max_names` | 6 | The names of a work searched in Prowlarr, 1 to 10. |
| `search.release_cache_minutes` | 10 | How long an answer of Prowlarr is reused, 0 to 1440. |
| `search.work_cache_hours` | 24 | How long an answer of a metadata source is reused, 0 to 720. |
| `placement.library.manga`, `.ebook`, `.audiobook` | `/data/files/comics`, `/data/files/ebooks`, `/data/files/audiobooks` | The folder of each library, as the placement worker sees it: an absolute path. Its library in Jellyfin is the one with a folder of the same name ([ADR 0016](adr/0016-placement.md)). |
| `waiting.interval_hours` | `6` | The hours between two searches of a waiting search: 1, 3, 6, 12 or 24 ([ADR 0017](adr/0017-waiting.md)). |
| `placement.merge_mp3` | on | The MP3 tracks of an audiobook merged into one M4B. |
| `placement.covers` | on | The cover of a series written when it has none (the first page of its first volume). |
| `placement.lock_jellyfin` | on | The name, the series, the number and the authors of a file placed set and locked in Jellyfin. |
| `discord.events.<event>` | on | The events of the journal sent to Discord: `sent`, `downloaded`, `placed`, `to_place`, `uploaded`, `retry`, `failed`, `misplaced`, `login`, `found` ([ADR 0015](adr/0015-journal.md)). Without the secret `discord.webhook`, nothing is posted. |

The secrets: `prowlarr.api_key`, `qbittorrent.api_key`, `jellyfin.api_key`, `sources.myanimelist.client_id`, `discord.webhook`. Sealed with AES-GCM under `SHELFDROP_SECRET_KEY`, opened in memory at the time of a call, never logged nor shown.

Read by Compose alone (`docker/compose.yaml`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `SHELFDROP_API_PORT` | `8000` | The loopback port of the API on the machine. |
| `SHELFDROP_PROXY_ADDRESS` | `127.0.0.1` | The address of the reverse proxy, given to uvicorn as `FORWARDED_ALLOW_IPS`. |
| `SHELFDROP_MEDIA_DIR` | `../.data/media` | The folder of the torrents and of the libraries the placement worker mounts on `/data` (NAMI: `/mnt/storage/data`). |
| `SHELFDROP_LIBRARY_GID` | `1000` | The group of the placement worker: the group of the files of qBittorrent and of the libraries. |
