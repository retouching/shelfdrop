# API

Every route but `/health` and the pages is served under the prefix `/api` (`SHELFDROP_API_PREFIX`). Its OpenAPI document (the routes open to the access tokens) is served at `/api/v1/openapi.json` and shown by Swagger UI at `/api/docs` ([ADR 0021](adr/0021-openapi.md)); this page describes every route, those of the session included.

## Session
Every route of the API but `POST /api/v1/session`, `GET /api/v1/setup` and `POST /api/v1/setup/account` needs the session cookie `__Host-shelfdrop`, or an access token where one may go, otherwise `401 not_signed_in` ([ADR 0013](adr/0013-sign-in-and-sessions.md)). Until the end of the set-up of the first launch, every route of the API and `/mcp` answer `409 setup_required` but the set-up, the session and the settings ([below](#set-up-of-the-first-launch)). A write (`POST`, `PUT`, `PATCH`, `DELETE`) with the cookie needs an `Origin` header naming the host of the request, otherwise `403 origin_refused`, before any other check.

### Access tokens
A program sends `Authorization: Bearer sd_...` instead of the cookie ([ADR 0020](adr/0020-access-tokens.md)); with that header the cookie is never read and no `Origin` is needed. A token unknown, expired or revoked gets `401 not_signed_in`; past 60 requests in a minute, `429 too_many_requests`. A token never reaches the settings, the trackers, the filters, the tokens, the logs, internal account nor the session (`403 token_forbidden`). Every token reads; a write (a download sent or tried again, a file placed, a waiting search, an upload, a merge of works, a series of Jellyfin changed) needs a token `write` (Read and download), else `403 token_forbidden`; a search of releases (`POST /api/v1/searches`) is a read.

### GET /api/v1/tokens, POST /api/v1/tokens, DELETE /api/v1/tokens/{id}
The session alone. `GET`: the tokens not revoked, the newest first, never a secret: `{"tokens": [{"id": 1, "name": "Agent", "scope": "write", "created_by": "admin", "created_at": 1792598400, "expires_at": null, "last_used_at": 1792602000}]}` (Unix seconds; `expires_at` null: without end). `POST {"name": "Agent", "scope": "read" | "write", "days": 30 | 90 | 365 | null}`: `201 {"token": {...}, "secret": "sd_..."}`, the one time the secret is given. `DELETE`: `204`, the token is refused from the next request; `404 token_not_found` for a token unknown or revoked already. Both go to the audit.

### POST /api/v1/session
`{"username": "...", "password": "..."}`: the internal account, when the name is its own (in any case; its password checked against its scrypt, Jellyfin not asked), otherwise an account of Jellyfin, an administrator. `200 {"username": "admin", "internal": false}`, the name of the internal account or the one Jellyfin gives, and the cookie `__Host-shelfdrop` (`Secure; HttpOnly; SameSite=Strict; Path=/`, 30 days). Errors: `401 login_refused` (wrong credentials, or an account of Jellyfin that is not an administrator or is disabled: the same answer), `429 too_many_attempts` (5 a minute from one address, 30 an hour in all), `503 jellyfin_unavailable` (Jellyfin does not answer, or `jellyfin.url` is not set), `422 validation_failed`.

### GET /api/v1/session, DELETE /api/v1/session
`GET`: `200 {"username": "admin", "internal": false}`, the account of the session (`internal`: the internal account). `DELETE`: `204`, the session ends here and in Jellyfin (none for the internal account), and the cookie is cleared.

### GET /api/v1/account, POST /api/v1/account, PUT /api/v1/account/password
The internal account, the session alone. `GET`: `{"account": {"username": "owner", "created_at": 1792598400, "password_changed_at": 1792598400}}`, or `{"account": null}` without one. `POST {"username": "owner", "password": "..."}` (a name of 1 to 64 characters without a space at either end, a password of 10 to 1024): `201` and the account; `409 account_exists` when there is one. `PUT /password {"current": "...", "new": "..."}`: `200` and the account; `422 password_refused` for a wrong current password, `404 account_not_found` without an account; every other session of the internal account ends. A `422 validation_failed` never repeats a password.

### Set-up of the first launch
[ADR 0024](adr/0024-first-launch-setup.md). `GET /api/v1/setup`, to anyone: `{"needed": true, "account": false}` (`needed`: the set-up is not finished; `account`: the internal account exists). `POST /api/v1/setup/account {"username", "password"}`, to anyone while the set-up is needed and no account exists: the internal account, and its session opened as by `POST /api/v1/session` (`200 {"username": "owner", "internal": true}` and the cookie); `409 account_exists` once an account exists (the first request wins), `409 setup_done` once the set-up is not needed. The steps of the services, the libraries and the uploads go through [the settings](#get-apiv1settings-put-apiv1settings) and [their tests](#post-apiv1settingstest). `POST /api/v1/setup/finish`, the session alone: `200 {"needed": false, "account": true}` once the Jellyfin saved answers its test; `409 jellyfin_not_connected` otherwise, `409 setup_done` when the set-up is not needed. While it is needed, every other route of the API and `/mcp` answer `409 setup_required`; `/health` and the pages do not.

## OpenAPI
The public document: the routes an access token reaches, with the scope each needs (`x-access`: `read`, `write`), its bodies and examples, and the error body ([ADR 0021](adr/0021-openapi.md)): [docs/openapi.public.json](openapi.public.json) in the repository, `GET /api/v1/openapi.json` and the page `GET /api/docs` (Swagger UI: an operation is tried there with a token, by Authorize) for a session or any token (`401 not_signed_in` without one). The routes of the session (the sign-in, the settings, the trackers, the filters, the tokens, the logs, internal account, the set-up) are not in it; [docs/openapi.json](openapi.json), in the repository alone, documents every route, with `public` and `session` too.

## MCP server
`POST /mcp`: the MCP server ([ADR 0022](adr/0022-mcp-server.md)), Streamable HTTP, stateless, JSON answers, with `Authorization: Bearer <token>` (without one, or one refused: `401 not_signed_in` and `WWW-Authenticate: Bearer`; past 60 requests a minute: `429 too_many_requests`). Its tools answer the schemas of the routes they mirror:

| Tool | Scope | Arguments | Answer, as the route |
|---|---|---|---|
| `search_works` | read | `query`, `kind` (`manga` by default) | `GET /api/v1/works` |
| `search_releases` | read | `kind`, `title`, `names`, `mode` (`work` by default, or `manual`), `refresh` | `GET /api/v1/searches/{id}` once the search ended |
| `grab_releases` | write | `search_id`, `releases` (`[{"id", "volumes"}]`), `work_id`, `author`, `series` | `POST /api/v1/downloads`, sent under the name of the token |
| `list_downloads` | read | none | `GET /api/v1/downloads` |
| `retry_download` | write | `download_id` | `POST /api/v1/downloads/{id}/retry` |
| `list_files_to_place` | read | `query` (empty by default) | `GET /api/v1/place/items` |
| `place_file` | write | `item_id`, `request` (the body of `POST /api/v1/place/items/{id}/link`) | that route |

A refusal is a tool error whose text starts with the code of the API (`token_forbidden: ...`, `search_not_found: ...`).

## Responses
Every response carries `X-Request-ID`: the value the request sent, when it is 1 to 128 characters among `A-Z a-z 0-9 . _ -`, otherwise a new one. The same id is in every log record of the request.

The answers of the API (`/api/...` and `/health`) carry `Cache-Control: no-store`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`. The pages carry the same headers but `Cache-Control`, and a policy that lets them load their scripts, styles and fonts from the same origin and their images from any HTTPS origin (the covers). The page `/api/docs` keeps `Cache-Control: no-store`, with a policy of its own: its scripts, its styles and its requests to the same origin, its images there or in `data:`, nothing inline.

## Errors
Every error body is:

```json
{"code": "work_not_found", "detail": "Work not found", "data": null}
```

`code` is stable and is what a client branches on; `detail` is for a human; `data` holds the details of some codes, otherwise `null`. The codes, with their status, are the members of `shelfdrop.http.errors.types.ErrorCode`, each documented by its comment. A `422` never repeats the values sent.

## GET /health
`200 {"status": "ok"}` as soon as the application serves requests. No database, no source. Logged at `DEBUG` when it succeeds.

## GET /api/v1/works
The search of a work in every metadata source of its family at once.

| Parameter | | |
| --- | --- | --- |
| `q` | required, 1 to 200 characters | The text searched: a title in any language, an author, or an ISBN. It needs 2 letters or digits. |
| `kind` | `manga` (default), `ebook` or `audiobook` | `manga` asks the manga sources, the two others the book sources. |

`200`:

```json
{
  "query": "Chainsaw Man",
  "kind": "manga",
  "works": [
    {
      "id": "mangaupdates:75336092483",
      "title": "Chainsaw Man",
      "shelf_name": "Chainsaw Man",
      "authors": ["Tatsuki Fujimoto"],
      "year": 2018,
      "volumes": 24,
      "volumes_fr": 22,
      "form": "manga",
      "names": [{"title": "Chainsaw Man", "language": "en", "checked": true, "sources": ["mangaupdates", "kitsu"], "source": "mangaupdates"}],
      "sources": ["mangaupdates", "kitsu", "mangadex", "wikidata", "bnf"],
      "cover_url": "https://...",
      "isbns": ["9782505..."],
      "links": {"mangaupdates": "https://www.mangaupdates.com/..."}
    }
  ],
  "other_forms": [],
  "unavailable": ["anilist"]
}
```

- `works`: at most 12, the best first. `other_forms`: for a manga search, the novels, anthologies and dōjinshi found, apart.
- `title`, `shelf_name`: the title shown and the name of the work in the library, chosen in the orders of the settings `search.source_order` and `search.language_order` ([configuration](configuration.md#settings-of-the-page)); by default the title of the most trusted source and the title of its French edition when there is one.
- `names`: every name of the work; `checked` names are the ones searched in the indexers by default: French, English and romaji names, and the title of the work. `language` is `fr`, `en`, `ja-ro` (romaji), `ja`, `pl`, `tr`... given by a source or told by the name itself, or `latin` when neither says: such a name is shown, unchecked. `sources`: the sources that gave the name, the most trusted first (`search.source_order`), and `source` the first of them (`[]` and `null` for a work found before the sources of its names were kept).
- `volumes`: the volumes of the original edition; `volumes_fr`: those published in France.
- `form`: `manga`, `novel`, `anthology`, `doujinshi`, `oneshot` or `other`.
- `unavailable`: the sources that did not answer; the works come from the others. `?retry=true` asks the sources resting after two failures in a row too (the page shows `unavailable` with a Retry button).
- `merge_id`, `parts`: a work the page joined from several by hand (`POST /api/v1/works/merges`) has the id of its merge and the works it joined, as the search found them alone (`{"id", "title", "authors", "sources"}`); `null` and `[]` otherwise.

Errors: `422 query_too_short`, `422 validation_failed`, `503 sources_unavailable` (no source of the family answered).

## POST /api/v1/searches
Starts a search of releases in Prowlarr, or joins the same one running.

```json
{"mode": "work", "kind": "manga", "title": "Jujutsu Kaisen", "names": ["Jujutsu Kaisen", "Sorcery Fight"], "refresh": false}
```

- `mode`: `work` (the names of a work: 6 at most, the setting `search.max_names`; a release that misses a word of its name is set aside) or `manual` (one text, as typed).
- `refresh`: ask Prowlarr again instead of the answers kept (10 minutes by default).

`200`, the progress:

```json
{"id": "Xb3...", "mode": "work", "kind": "manga", "title": "Jujutsu Kaisen", "state": "queued",
 "names": [{"name": "Jujutsu Kaisen", "state": "queued", "found": 0}],
 "queued_ahead": 1, "followers": 1, "fetched_at": null}
```

- `state`: `queued`, `running`, `done`, or `failed` when no name got an answer. A name: `queued`, `running`, `done`, `failed` (error or 60 seconds).
- `queued_ahead`: the other searches before it while it waits; `followers`: the requests that asked it (more than one: shared); `fetched_at`: Unix seconds of the oldest answer of Prowlarr (a kept one may be minutes old).

Errors: `422 query_too_short`, `422 too_many_names`, `422 validation_failed`, `503 prowlarr_unavailable` (the trackers were never read and Prowlarr does not answer, or its address or key is not saved).

## GET /api/v1/searches/{id}
The progress and the releases found so far, scored and ranked with the filters and the trackers of now; a search is kept 10 minutes after its end.

```json
{"progress": {...}, "minimum": -100, "releases": [
  {"id": "3f1c...", "title": "Jujutsu.Kaisen.T01.FRENCH.MANGA.CBZ.eBook-PapriKa+", "matched_name": "Jujutsu Kaisen",
   "indexer_id": 2, "indexer": "The Old School", "indexer_rank": 1, "info_url": "https://...", "info_hash": "...",
   "seeders": 30, "size": 99614720, "volumes": {"kind": "single", "first": 1, "last": 1},
   "score": 100, "score_rules": [{"name": "Français", "score": 100}], "rejected": null, "automatic": true}]}
```

- In the order of the page: packs and complete editions first, then volume by volume; for one volume, the score, the order of the trackers, the seeds. No release without seeds; one found twice once.
- `volumes.kind`: `single`, `range`, `complete` or `unknown`.
- `rejected`: `relevance` (its title misses a word of its name), `score` (under `minimum`), or `null`.
- `automatic`: kept, and from a tracker whose `auto` is on: a [download](#post-apiv1downloads) of a work may take it.
- The download link of Prowlarr is never in the answer: it carries its key.

Errors: `404 search_not_found`.

## GET /api/v1/releases/{id}/torrent
The torrent of a release of a search kept, asked to Prowlarr: `200` with the `.torrent` file (`application/x-bittorrent`), or `303` to its magnet link. Errors: `404 release_not_found` (no search kept holds it, or Prowlarr gave no download link), `503 prowlarr_unavailable`.

## GET /api/v1/searches/{id}/events
Server-Sent Events: a `progress` event (the object of `POST`) now and at each change, then an `end` event. `404 search_not_found`.

## POST /api/v1/downloads
Sends releases of a search kept to the torrent client ([ADR 0014](adr/0014-downloads.md), [ADR 0025](adr/0025-torrent-clients.md)):

```json
{"search_id": "Xb3...", "work_id": "mangaupdates:75336092483", "author": "Tatsuki Fujimoto", "series": "Chainsaw Man",
 "releases": [{"id": "3f1c...", "volumes": {"kind": "range", "first": 1, "last": 11}}]}
```

- The search decides the mode: the search of a work gives automatic downloads, into the category of the torrent client of its kind (`manga`, `ebook`, `audiobook`; a label on Deluge and Transmission), with `work_id`, `author` and `series` (200 characters at most each); a manual search gives manual ones, into `shelfdrop-manual`, without them.
- `volumes`: as the page gives them (`single`, `range`, `complete`, `unknown`; `first`, `last` 0 to 9999). A release given twice is sent once; 100 releases at most.

`200 {"downloads": [...]}`, the downloads created, each `waiting`: the send goes on after the answer. Errors: `404 search_not_found` (a search ended more than 10 minutes ago), `422 release_not_in_search` (`data.ids`: releases the search does not hold, or without a download link), `422 release_not_automatic` (`data.ids`: releases of the search of a work set aside or from a tracker whose `auto` is off), `422 validation_failed`. Nothing is sent on an error.

## GET /api/v1/downloads
The 200 newest downloads, the newest first, each as the torrent client has it now:

```json
{"downloads": [{"id": 4, "title": "Chainsaw.Man.T01-T11.FRENCH.CBZ.eBook-PapriKa+", "indexer": "Nyaa.si", "size": 1073741824,
  "info_hash": "c12fe1c0...", "mode": "auto", "kind": "manga", "category": "manga", "work_id": "mangaupdates:75336092483",
  "work_name": "Chainsaw Man", "author": "Tatsuki Fujimoto", "series": "Chainsaw Man",
  "volumes": {"kind": "range", "first": 1, "last": 11},
  "progress": {"state": "downloading", "percent": 77, "speed": 4404019, "eta": 96, "reason": null, "destination": null, "unplaced": null, "copied": false},
  "attempts": 1, "created_at": 1792598400, "created_by": "admin"}]}
```

- `progress.state`: `waiting` (being sent, or waiting in the torrent client: queued, checked, fetching its metadata, stopped, stopped on an error, or not listed), `downloading` (with `percent` 0 to 100, `speed` in bytes a second, `eta` in seconds, 0 when unknown), `placing` (an automatic download complete, being placed; `percent` while its MP3 tracks are merged), `placed` (`destination`: the library and the series, « BD & Mangas › Berserk »), `to_place` (placed by hand, `unplaced` says why: `manual`, a manual download; `chapters`, `no_volume`, `unknown_author`, `no_files`, `missing_files`, `link_refused`, `copy_failed`, `merge_failed`: what the placement could not do alone), `failed` (`reason`: `not_received`, or `duplicate`, a torrent the client already had). `progress.copied`: a file of it was copied on the shelf rather than hardlinked (`placement.mode`, [ADR 0016](adr/0016-placement.md)).
- `work_name`: the name of the work, or the text of a manual search. `created_by`: the account that sent it.
- The torrent client down: the downloads sent show as `waiting`.

## POST /api/v1/downloads/{id}/retry
Sends a torrent the torrent client did not receive again: the same torrent, into the same category, one more attempt. `200`, the download, `waiting`. Errors: `404 download_not_found`, `409 download_not_retryable` (a duplicate, or a download not failed).

## GET /api/v1/downloads/{id}/cover
The cover of the work of an automatic download, for the page: read by the API at the sources of the work (a work a search returned in the last 7 days), kept an hour in its memory. `200`, the picture (`image/jpeg`, `image/png` or `image/webp`) with `Cache-Control: private, max-age=3600`. Errors: `404 download_not_found`, `404 download_cover_not_found` (a manual download, a work whose search is older than 7 days, or one its sources give no picture of).

## GET /api/v1/trackers, POST /api/v1/trackers/refresh, PUT /api/v1/trackers
The indexers of Prowlarr, in their order, with their categories: `{"trackers": [{"indexer_id": 1, "name": "Nyaa.si", "language": "en-US", "prowlarr_enabled": true, "used": true, "auto": true, "available_categories": [{"id": 7030, "name": "Books/Comics"}, {"id": 100920, "name": "Literature"}], "categories": {"manga": [7030, 100920], "ebook": [], "audiobook": [3030]}, "default_categories": false}]}`. `available_categories`: the categories Prowlarr gave at its last read (`capabilities.categories`), a sub-category under the name of its parent, an indexer's own category from 100000; then the standard categories chosen or by default it did not give, with their Newznab name (`Books/Comics`). A `GET` while a tracker in use never had its categories read reads the indexers of Prowlarr first (Prowlarr down: the trackers saved). `categories`: the categories searched for each kind; never chosen (`default_categories`), 7030 for `manga`, 7020 for `ebook`, 3030 for `audiobook`; an empty list: the tracker is not asked for that kind. `refresh` reads `GET /api/v1/indexer` of Prowlarr again (`503 prowlarr_unavailable`). `PUT` takes `{"trackers": [{"indexer_id", "used", "auto", "categories"}]}` in the new order; a tracker left out keeps its choices and comes after; a tracker not asked is never automatic; `categories` absent or `null` keeps those saved, and the default ones for every kind are the default again. A category the tracker does not know (neither in `available_categories`, nor the default of the kind, nor already chosen): `422 unknown_tracker_category`, `data.indexer_ids` the trackers, nothing saved.

## GET /api/v1/filters, PUT /api/v1/filters
`{"rules": [{"name": "Français", "pattern": "\\b(FRENCH|VF)\\b", "regex": true, "score": 100, "kinds": [], "enabled": true}], "minimum": -100}`. A rule of words matches whole words, any case, separated by commas; `kinds` empty: every kind. `PUT` replaces them; a rule whose expression is empty or invalid: `422 invalid_filter_rule`, `data.positions` its places, nothing saved.

## GET /api/v1/works/cover

`?id=<work id>`: the cover of a work kept from a search (7 days), read by the API at its source (a JPEG, a PNG or a WebP, 5 MB at most), `Cache-Control: private, max-age=86400`. The id goes in the query, since some hold slashes (`bnf:http://...`). A work unknown, older than its search, or whose sources give no picture: `404 work_cover_not_found`. The search page loads it for each work whose `cover_url` is not `null`.

## GET /api/v1/works/{id}
A work a search returned in the last 7 days, the same object as an item of `works`. `404 work_not_found` otherwise.

## POST /api/v1/uploads, PUT /api/v1/uploads/{id}/chunks/{n}, POST /api/v1/uploads/{id}/finish
A file sent from the Manual page in chunks ([ADR 0019](adr/0019-uploads.md)). `POST` `{"name": "Berserk T41.cbz", "size": 52429800}`: `201` a new upload, `200` the one of the same name and size still receiving (resumed): `{"id": 3, "name": "Berserk T41.cbz", "size": 52429800, "chunk_size": 52428800, "chunks": 2, "received": [0], "state": "receiving"}`; `422 upload_refused` with `data.reason` `type` (not an EPUB, PDF, CBZ, CBR, M4B, MP3 or ZIP), `size` (empty, over 5 GiB) or `name`. `PUT` takes chunk `n` as `application/octet-stream` (`chunk_size` bytes, the last one the rest) and answers the upload; `422 chunk_refused` (out of the file, another length), `404 upload_not_found`, `409 upload_done` (checked already, or corrupt). `finish` takes `{"sha256": "<hex>"}` of the whole file: `200` `verified` (the placement worker lists it in Place at its next round, `origin` `upload`), `422 chunk_refused` (chunks missing), `422 upload_corrupt` (another SHA-256: the file is removed, to send again).

## POST /api/v1/works/merges, DELETE /api/v1/works/merges/{id}
Works joined by hand into one, for every search of their family after (`manga`, or `book` for the ebooks and the audiobooks): `{"kind": "manga", "work_ids": ["kitsu:1", "bnf:ark"], "shelf_name": "L'Atelier des sorciers"}`, the ids of works a search returned in the last 7 days, 2 to 20 of them; a merge among them (its `id`) takes the others, and the merges they belonged to give way. `201` `{"id": 3, "family": "manga", "keys": ["kitsu:1", "bnf:ark"], "shelf_name": "L'Atelier des sorciers"}`: the next searches give one work in the place of the first, built from every member, under that name. Errors: `404 work_not_found`, `422 work_merge_refused` (fewer than two distinct works, an empty name), `422 validation_failed`. `DELETE` splits it: `204`, or `404 work_merge_not_found`.

## GET /api/v1/settings, PUT /api/v1/settings
The settings of the page ([the list](configuration.md#settings-of-the-page)):

```json
{"values": {"prowlarr.url": "http://prowlarr:9696", "search.max_names": 6, "sources.kitsu.enabled": true, "search.language_order": ["fr", "en", "ja-ro", "latin"]},
 "secrets": {"prowlarr.api_key": 1792598400, "torrent.api_key": null},
 "torrent_clients": ["qui", "qbittorrent", "deluge", "transmission"]}
```

- `values`: every setting, its default when never saved. `secrets`: when each secret was set (Unix seconds), or `null`; never its value. `torrent_clients`: the values of `torrent.client` this version can use (a connector serves each).
- `PUT` takes `{"values": {...}, "secrets": {"prowlarr.api_key": "new key", "jellyfin.api_key": null}}`: the keys given alone change, `null` clears a secret. Each change is audited (who, when, which key), never its value. Errors: `422 invalid_settings`, `data.keys` the keys unknown or whose value is refused, nothing saved. An order (`search.language_order`, `search.source_order`) is a list of every value it orders, each once.

## POST /api/v1/settings/test
The test of a connection, with the values typed before they are saved: `{"service": "prowlarr", "url": null, "secret": null}`. `service`: `prowlarr`, `torrent` (the torrent client), `jellyfin`, or a metadata source (`kitsu`, `myanimelist`...); `url` and `secret` `null` are the values saved, a `secret` `""` none. The torrent client alone takes `client` (`qui`, `qbittorrent`, `deluge`, `transmission`) and `username`, `null` the values saved, a `username` `""` none; its `secret` is the key of qui or the password of the others, the one saved being the one of the client tested.

```json
{"service": "prowlarr", "ok": true, "state": "connected", "status": null, "version": "2.1.5.5216",
 "count": 4, "missing": [], "elapsed_ms": null, "client": null, "reason": null}
```

- `state`: `connected`, `no_address`, `no_key` (the key, or a credential the torrent client signs in with: the key of qui, the username and the password of qBittorrent, the password of Deluge, both or none for Transmission), `refused` (`status` 401 or 403), `unavailable` (no answer, or an error with its `status`); the torrent client also `unsupported` (it answers, shelfdrop cannot send to it: `reason` `label-plugin`, Deluge without its plugin Label, or `transmission-version`, Transmission before 3.00) and `no_connector` (no connector of this version serves the client).
- Prowlarr: `version`, `count` the indexers on. The torrent client: `client`, `version`, `count` the categories of shelfdrop found (`manga`, `ebook`, `audiobook`, `shelfdrop-manual`), `missing` the others. Jellyfin: `version`, `count` its libraries of books. A source: `elapsed_ms`, the time of a fixed search.

Errors: `422 invalid_settings` (an unknown service, an address, a client or a username refused, or a `client` or a `username` given to another service: `data.keys`, `<service>.url`, `<service>.client`, `<service>.username`).

## GET /api/v1/settings/health
The last tests of the background, run at start then every 5 minutes, of each service whose address and key are saved (the torrent client: its address): `{"services": [<the object of the test>], "checked_at": 1792598400}`.

## GET /api/v1/settings/audit
The last 100 changes, the newest first: `{"entries": [{"at": 1792598400, "actor": "admin", "action": "replaced", "target": "prowlarr.api_key"}]}`. `action`: `changed`, `replaced`, `cleared`, `imported` (`actor` `environment`); the target `trackers` or `filters` for a change of those; `created`, `revoked` for an access token (target `token.<id>`).

## GET /api/v1/library/series
The series of the libraries of books of Jellyfin (the library of each kind, found by the name of its folder, [ADR 0016](adr/0016-placement.md)): the folders of their series (`<Series>/` of a manga, `<Author>/<Series>/` of a book) and the books under each, by name. `image_tag`: the tag of the image of the series in Jellyfin (`ImageTags.Primary`, F40), which changes with the image, `null` without one. `503 jellyfin_unavailable` when Jellyfin does not answer or its address or key is not set.

```json
{"series": [{"id": "f2c1...", "kind": "manga", "name": "Berserk", "original_title": "", "authors": ["Kentaro Miura"],
  "year": 1990, "genres": ["Seinen"], "summary": "", "has_image": true, "volumes": 42,
  "volumes_without_summary": 42, "volumes_without_image": 0, "image_tag": "9f2c..."}]}
```

## GET /api/v1/library/series/{id}/proposals
What the page proposes for a series: the images of its volumes (`volumes`: `item_id`, `label` « Tome 3 · CBZ », in French, `number` the number of the volume, `null` without one, `format` `CBZ`, `EPUB` or `M4B`, `image_tag`), then the covers, the summaries and the names of its work: the work it was linked to (`linked: true`, `PUT .../work`), else the first the sources find under its name (`covers`, `summaries`: `source`, and `url` or `text`; `names`: `title`, `language`, `sources`, `source`, as the work search gives them, the proposals of its title; empty when no source answers). `work_id` and `work` (`id`, `title`, `shelf_name`, `authors`, `year`, `sources`, `cover_url`: its cover at `/api/v1/works/cover?id=`), `null` without one. `404 series_not_found`, `503 jellyfin_unavailable`.

## PUT /api/v1/library/series/{id}/work, DELETE /api/v1/library/series/{id}/work
`PUT {"work_id": "kitsu:9"}`: the series linked to a work a search returned in the last 7 days, in the place of the first work found under its name (a mismatch): kept (`series_links`), its proposals come from it after, read from the cache of the search, else searched again under its name; the files placed in the folder of the series (`files`) take its id, so that the sync and the volumes on the shelf follow it. `DELETE`: the link undone, the work is again the one found under its name (the files keep their work). Both answer the proposals, as `GET .../proposals`. `404 series_not_found`, `404 work_not_found`, `503 jellyfin_unavailable`.

## GET /api/v1/library/series/{id}/adoption, POST /api/v1/library/series/{id}/adoption
The files of a series shelfdrop did not place (added by hand), adopted as its own ([ADR 0016](adr/0016-placement.md)). `GET`: the preview, `{"series_id", "work_id", "files": [...]}`, `work_id` its work (as for the proposals; `null`: nothing can be adopted); each volume in Jellyfin: `item_id`, `path` (as Jellyfin sees it), `size`, the number proposed (`volume` or `chapter`: its `IndexNumber`, else a chapter or a volume its file name gives, read as the placement reads them; else both `null`), `origin` (`jellyfin`, `name`, `null`), `target` (the name it would take in its folder: `<Series> - T03.cbz`, `<Series> - Ch. 120.cbz`; `null` without a number), `adopted` (on the shelf already). `POST {"items": [{"item_id", "volume", "chapter", "include"}], "place": false}`: the files included recorded on the shelf (`files`) as files of the work, under the numbers given, untouched; with `place`, the placement worker renames each to its `target` in the same folder first, at its next round (a hardlink to the new name, then the old one removed; never over a file), then records them and asks Jellyfin to refresh the folder. Answers `{"adopted": 2, "renamed": true, "conflicts": ["<item id>"]}`: `conflicts`, the files whose name is taken by another file of the folder, adopted under their name. Nothing is done when a file is refused: `422 adoption_refused`, `data.reason` `no_work`, `unknown` (no volume of the series), `adopted`, `unnumbered` (neither a volume nor a chapter), `duplicate` (a number another file included, or the shelf, holds), `data.item_ids` the files. `404 series_not_found`, `503 jellyfin_unavailable`.

## GET /api/v1/library/series/{id}/volumes
A series (as `GET /api/v1/library/series` gives it), its volumes by number and the numbers missing: those between 1 and the highest held (by the number of a volume in Jellyfin, else in the name of its file) that no volume holds. Each volume: `id` (its item in Jellyfin), `type` (`Book`, `AudioBook`), `name`, `number` (`null` without one), `summary`, `authors`, `has_image`, `image_tag` (as for a series), `file_name`, `size` (bytes, `null` when Jellyfin does not tell it). `404 series_not_found`, `503 jellyfin_unavailable`.

```json
{"series": {"id": "f2c1...", "name": "Berserk", "...": "..."}, "volumes": [{"id": "9a0e...", "type": "Book",
  "name": "Berserk - T01", "number": 1, "summary": "", "authors": ["Kentaro Miura"], "has_image": true,
  "file_name": "Berserk - T01.cbz", "size": 73400320}], "missing": [2, 5]}
```

## GET /api/v1/library/items/{id}/file
The file of a book or an audiobook of a library of a kind, as Jellyfin sends it (`GET /Items/{id}/Download`, streamed): its type, its length when Jellyfin gives it, `Content-Disposition: attachment` with its name (in ASCII, and whole in `filename*`). Any other item (a folder, a library, another library) is `404 volume_not_found`, never asked of Jellyfin; `503 jellyfin_unavailable`.

## PUT /api/v1/library/items/{id}
`{"name", "number": null, "summary": "", "authors": [], "lock": true, "image": null}`: the fields of a volume set in Jellyfin, its authors in place of those it had (its other people kept), locked with `lock` (`Name`, `Overview`, `Cast`); `image` as for a series, set on the volume. Answers the volume read again (a new image, a new `image_tag`), then asks Jellyfin to refresh it, never replacing what was written (`metadataRefreshMode=FullRefresh`, `imageRefreshMode=Default`, `replaceAllMetadata=false`, `replaceAllImages=false`, F40); a refresh that fails is logged and fails nothing. `404 volume_not_found`, `422 image_refused`, `503 jellyfin_unavailable`.

## GET /api/v1/library/items/{id}/image?width=400&tag=
The image Jellyfin holds for a series or a volume (50 to 2000 pixels wide), through the session of the page. With `tag` (its `image_tag`, 64 characters at most: an address that changes with the image), `Cache-Control: private, max-age=31536000, immutable`; without, `private, max-age=60`. The page asks its images with their tag.

## PUT /api/v1/library/series/{id}
The fields of a series set in Jellyfin (`name`, `original_title`, `authors`, `year`, `genres`, `summary`), locked with `lock` (`Name`, `Genres`, `Cast`, `Overview`); `summary_to_volumes` copies the summary on its volumes without one. `image`: `{"kind": "item", "item_id"}` (the image of a volume), `{"kind": "url", "url"}` (read by shelfdrop, 5 MB at most) or `{"kind": "data", "data": "<base64>"}`; set on the series (`image_to_series`), on its volumes without one (`image_to_volumes`), and written as the `cover.jpg` of its folder by the placement worker (`save_cover`). Answers the series read again (a new image, a new `image_tag`), then asks Jellyfin to refresh its folder and its volumes, as for a volume. `404 series_not_found`, `422 image_refused` (not a JPEG, a PNG or a WebP of 5 MB at most: nothing is changed), `503 jellyfin_unavailable`.

## POST /api/v1/library/summaries
`{"summaries": {"<series id>": "<text>"}}`: each summary set on its series when it has none, and on its volumes without one, locked. Answers `{"series": <the number of series changed>}`.

## POST /api/v1/library/scan, GET /api/v1/library/scan
`POST {"mode": "new" | "missing" | "all", "kind": null, "series_id": null}` asks Jellyfin for a scan of a series, of the library of a kind, or of every library (`202`); `new` the new and changed files, `missing` the missing metadata and images, `all` everything replaced. Both answer the progress of the scan of each library, from 0 to 100, `null` when idle: `{"progress": {"manga": 42.5, "ebook": null}}`.

## POST /api/v1/library/sync, GET /api/v1/library/sync
`POST {"series_id": null}`: the metadata of the files placed by shelfdrop sent again to Jellyfin, for a series or for every library (`202`), in the background ([ADR 0016](adr/0016-placement.md)): the name, the series, the number, the sort and the authors of shelfdrop (over those of Jellyfin), `Name` and `Cast` locked; the images are left; whatever `placement.lock_jellyfin` says. Then the folder of each series whose items changed is refreshed in Jellyfin, once, as after a change of a volume. While a sync runs, `POST` starts none and answers its state. Both answer the state of the last sync: `{"stage": "done", "series_id": null, "changed": 12, "unchanged": 30, "not_found": 1, "started_at": 1792598400, "ended_at": 1792598406}`; `stage`: `idle` (none since the start of the API), `running`, `done`, `failed`; `not_found`: the files placed Jellyfin does not list. `404 series_not_found`, `503 jellyfin_unavailable`.

## GET /api/v1/waiting
The searches kept waiting ([ADR 0017](adr/0017-waiting.md)), the newest first, and the hours between two searches: `{"searches": [...], "every_hours": 6}`. Each: `id`, `work_id`, `title`, `author`, `kind`, `names`, `wanted` (`target` `any`, `volume` with `volume`, or `chapters` with `chapter_from` and `chapter_to`, `null` for every one after), `label` (« T03 », « Ch. 233 et suivants », « Toute release », in French; the page writes its own from `wanted`), `state` (`waiting` or `found`, with `releases`), `attempts`, `created_at`, `created_by`, `searched_at`, `next_search_at` (Unix seconds).

## POST /api/v1/waiting
`{"work_id", "title", "author", "kind", "names": [...], "wanted": [{"target": "volume", "volume": 3}, ...]}`: one search for each thing wanted, but those already waiting for the same work. Answers `{"added": [...], "skipped": 1}`. `422 validation_failed` for a volume without its number or chapters without their first.

## POST /api/v1/waiting/{id}/search, DELETE /api/v1/waiting/{id}
A search now (answers the search), or a removal (`204`). `404 waiting_not_found`.

## GET /api/v1/waiting/owned?kind=manga&title=Chainsaw%20Man&work_id=...
The volumes of a work already placed or in the library of its kind in Jellyfin: `{"volumes": [1, 2, 3]}`.

## GET /api/v1/place/items?q=
The files of the Place page ([ADR 0018](adr/0018-ranger.md)), the newest first, and the count of those to place: `{"items": [...], "open": 3}`. Each: `id` (`item-<n>`), `origin` (`download`, `library`, `upload`), `kind` (or `null`), `name`, `path` (as the worker sees it), `size`, `state` (`unlinked`, `chapters`, `misplaced`, `placed`, `ignored`, or `placing` while the worker has a request of it), `reason` (why its download was not placed: `manual`, `chapters`, `no_volume`...; why the scan found it: `root`, `naming`, `tracks`, `chapters`; `relink`), `error` (why the last request failed: `exists`, `link_refused`, `copy_failed`, `merge_failed`, `no_files`, `unknown_author`), `destination`, `chapters`, `existing` (the volumes of `series` on the shelf), `loose` (the chapters loose in the folder of `series`, out of its files, read again at each round of the worker: a volume of a release in chapters is complete with them too), `series`, `author`, `work_id`, `copied` (placed through a copy of a file of its download, `placement.mode`). With `q` (200 characters at most), the files of the shelf whose path holds it come after, `id` `shelf-<n>`, `placed`.

## POST /api/v1/place/items/{id}/link
What the worker does with a file of Place, at its next round: `202`, the file, `placing`. The body is one of:
- `{"type": "volume", "kind", "work_id", "series", "author", "volume", "title"}`: one volume (`volume` null: 1);
- `{"type": "chapter", "work_id", "series", "author", "first", "last", "volume"}`: one file of chapters, `last` and `volume` optional;
- `{"type": "chapters", "work_id", "series", "author", "summary", "volumes": [{"volume", "first", "last", "replace"}], "rest": "place" | "keep"}`: a release in chapters linked to its volumes;
- `{"type": "ignore"}`: the file left where it is, nothing written nor removed: `ignored`, out of the files to place (and of `open`); its download is `placed` once none of its files is left to place.

Errors: `404 place_item_not_found`, `409 place_item_busy` (placed, or a request waits), `422 place_request_refused` (chapters for a file not in chapters or a volume for one, volumes repeated, ranges upside down or overlapping, nothing to place), `422 validation_failed`.

## POST /api/v1/place/items/{id}/resume
An ignored file back among the files to place, at once: `200`, the file, `chapters` for a release in chapters, `misplaced` for a file of the libraries, `unlinked` otherwise. Its download, placed meanwhile, stays `placed`. Errors: `404 place_item_not_found`, `409 place_item_not_ignored`.

## POST /api/v1/place/shelf/{id}/link
A file of the shelf (`shelf-<n>`) placed again: the body of a volume; it becomes a file of Place of the libraries, moved by the worker. `202`, that file. `404 place_item_not_found`.

## POST /api/v1/place/scan
A scan of the libraries for the files misplaced, by the worker at its next round (one waiting at most): `202`.

## GET /api/v1/logs
The session alone ([ADR 0023](adr/0023-logs.md)). The records of a service, the newest first, from its file and its two rotated copies: `?service=api|placement` (`api` by default), `level` (the lowest shown: `DEBUG`, the default, `INFO`, `WARNING`, `ERROR`, `CRITICAL`), `text` (200 characters at most, searched without case in the message, the logger, the request id and the other fields), `limit` (1 to 1000, 200 by default), `before` (the `next` of the previous page). `{"entries": [{"timestamp": "2026-10-24T10:00:02.000+00:00", "level": "INFO", "logger": "shelfdrop.http.middleware.access_log", "message": "GET /api/v1/works 200 812.4ms", "request_id": "c0ffee", "fields": {"method": "GET", "path": "/api/v1/works", "status": 200, "duration_ms": 812.4, "client_ip": "127.0.0.1"}}], "next": "2026-10-24T10:00:02.000+00:00~1"}`: `fields` holds the other fields of the record (`exception`, `stack` among them); `next` null: no older entry. A service that never wrote has no entry. A wrong parameter: `422 validation_failed`. Its successes are logged at `DEBUG` alone.
