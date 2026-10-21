# API

Every route but `/health` and the pages is served under the prefix `/api` (`SHELFDROP_API_PREFIX`). The API serves neither its schema nor a documentation page: this page describes it.

## Session
Every route of the API but `POST /api/v1/session` needs the session cookie `__Host-shelfdrop`, otherwise `401 not_signed_in` ([ADR 0013](adr/0013-sign-in-and-sessions.md)). A write (`POST`, `PUT`, `PATCH`, `DELETE`) needs an `Origin` header naming the host of the request, otherwise `403 origin_refused`, before any other check.

### POST /api/v1/session
`{"username": "...", "password": "..."}`: an account of Jellyfin, an administrator. `200 {"username": "Sylvain"}`, the name Jellyfin gives, and the cookie `__Host-shelfdrop` (`Secure; HttpOnly; SameSite=Strict; Path=/`, 30 days). Errors: `401 login_refused` (wrong credentials, or an account that is not an administrator or is disabled: the same answer), `429 too_many_attempts` (5 a minute from one address, 30 an hour in all), `503 jellyfin_unavailable` (Jellyfin does not answer, or `jellyfin.url` is not set), `422 validation_failed`.

### GET /api/v1/session, DELETE /api/v1/session
`GET`: `200 {"username": "Sylvain"}`, the account of the session. `DELETE`: `204`, the session ends here and in Jellyfin, and the cookie is cleared.

## Responses
Every response carries `X-Request-ID`: the value the request sent, when it is 1 to 128 characters among `A-Z a-z 0-9 . _ -`, otherwise a new one. The same id is in every log record of the request.

The answers of the API (`/api/...` and `/health`) carry `Cache-Control: no-store`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`. The pages carry the same headers but `Cache-Control`, and a policy that lets them load their scripts, styles and fonts from the same origin and their images from any HTTPS origin (the covers).

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
      "names": [{"title": "Chainsaw Man", "language": "en", "checked": true}],
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
- `shelf_name`: the name of the work in the library, the title of its French edition when there is one.
- `names`: every name of the work; `checked` names are the ones searched in the indexers by default: French, English and romaji names, and the title of the work. `language` is `fr`, `en`, `ja-ro` (romaji), `ja`, `pl`, `tr`... given by a source or told by the name itself, or `latin` when neither says: such a name is shown, unchecked.
- `volumes`: the volumes of the original edition; `volumes_fr`: those published in France.
- `form`: `manga`, `novel`, `anthology`, `doujinshi`, `oneshot` or `other`.
- `unavailable`: the sources that did not answer; the works come from the others.

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
Sends releases of a search kept to qBittorrent ([ADR 0014](adr/0014-downloads.md)):

```json
{"search_id": "Xb3...", "work_id": "mangaupdates:75336092483", "author": "Tatsuki Fujimoto", "series": "Chainsaw Man",
 "releases": [{"id": "3f1c...", "volumes": {"kind": "range", "first": 1, "last": 11}}]}
```

- The search decides the mode: the search of a work gives automatic downloads, into the category of qBittorrent of its kind (`manga`, `ebook`, `audiobook`), with `work_id`, `author` and `series` (200 characters at most each); a manual search gives manual ones, into `shelfdrop-manual`, without them.
- `volumes`: as the page gives them (`single`, `range`, `complete`, `unknown`; `first`, `last` 0 to 9999). A release given twice is sent once; 100 releases at most.

`200 {"downloads": [...]}`, the downloads created, each `waiting`: the send goes on after the answer. Errors: `404 search_not_found` (a search ended more than 10 minutes ago), `422 release_not_in_search` (`data.ids`: releases the search does not hold, or without a download link), `422 release_not_automatic` (`data.ids`: releases of the search of a work set aside or from a tracker whose `auto` is off), `422 validation_failed`. Nothing is sent on an error.

## GET /api/v1/downloads
The 200 newest downloads, the newest first, each as qBittorrent has it now:

```json
{"downloads": [{"id": 4, "title": "Chainsaw.Man.T01-T11.FRENCH.CBZ.eBook-PapriKa+", "indexer": "Nyaa.si", "size": 1073741824,
  "info_hash": "c12fe1c0...", "mode": "auto", "kind": "manga", "category": "manga", "work_id": "mangaupdates:75336092483",
  "work_name": "Chainsaw Man", "author": "Tatsuki Fujimoto", "series": "Chainsaw Man",
  "volumes": {"kind": "range", "first": 1, "last": 11},
  "progress": {"state": "downloading", "percent": 77, "speed": 4404019, "eta": 96, "reason": null},
  "attempts": 1, "created_at": 1792598400, "created_by": "Sylvain"}]}
```

- `progress.state`: `waiting` (being sent, or waiting in qBittorrent: queued, fetching its metadata, stopped, or not listed), `downloading` (with `percent` 0 to 100, `speed` in bytes a second, `eta` in seconds, 0 when unknown), `placing` (an automatic download complete), `to_place` (a manual one complete: placed by hand), `failed` (`reason`: `not_received`, or `duplicate`, a torrent qBittorrent already had).
- `work_name`: the name of the work, or the text of a manual search. `created_by`: the account that sent it.
- qBittorrent down: the downloads sent show as `waiting`.

## POST /api/v1/downloads/{id}/retry
Sends a torrent qBittorrent did not receive again: the same torrent, into the same category, one more attempt. `200`, the download, `waiting`. Errors: `404 download_not_found`, `409 download_not_retryable` (a duplicate, or a download not failed).

## GET /api/v1/trackers, POST /api/v1/trackers/refresh, PUT /api/v1/trackers
The indexers of Prowlarr, in their order: `{"trackers": [{"indexer_id": 1, "name": "Nyaa.si", "language": "en-US", "prowlarr_enabled": true, "used": true, "auto": true}]}`. `refresh` reads `GET /api/v1/indexer` of Prowlarr again (`503 prowlarr_unavailable`). `PUT` takes `{"trackers": [{"indexer_id", "used", "auto"}]}` in the new order; a tracker left out keeps its choices and comes after; a tracker not asked is never automatic.

## GET /api/v1/filters, PUT /api/v1/filters
`{"rules": [{"name": "Français", "pattern": "\\b(FRENCH|VF)\\b", "regex": true, "score": 100, "kinds": [], "enabled": true}], "minimum": -100}`. A rule of words matches whole words, any case, separated by commas; `kinds` empty: every kind. `PUT` replaces them; a rule whose expression is empty or invalid: `422 invalid_filter_rule`, `data.positions` its places, nothing saved.

## GET /api/v1/works/{id}
A work a search returned in the last 7 days, the same object as an item of `works`. `404 work_not_found` otherwise.

## GET /api/v1/settings, PUT /api/v1/settings
The settings of the page ([the list](configuration.md#settings-of-the-page)):

```json
{"values": {"prowlarr.url": "http://prowlarr:9696", "search.max_names": 6, "sources.kitsu.enabled": true},
 "secrets": {"prowlarr.api_key": 1792598400, "qbittorrent.api_key": null}}
```

- `values`: every setting, its default when never saved. `secrets`: when each secret was set (Unix seconds), or `null`; never its value.
- `PUT` takes `{"values": {...}, "secrets": {"prowlarr.api_key": "new key", "jellyfin.api_key": null}}`: the keys given alone change, `null` clears a secret. Each change is audited (who, when, which key), never its value. Errors: `422 invalid_settings`, `data.keys` the keys unknown or whose value is refused, nothing saved.

## POST /api/v1/settings/test
The test of a connection, with the values typed before they are saved: `{"service": "prowlarr", "url": null, "secret": null}`. `service`: `prowlarr`, `qbittorrent`, `jellyfin`, or a metadata source (`kitsu`, `myanimelist`...); `url` and `secret` `null` are the values saved, a `secret` `""` none.

```json
{"service": "prowlarr", "ok": true, "state": "connected", "status": null, "version": "2.1.5.5216",
 "count": 4, "missing": [], "elapsed_ms": null}
```

- `state`: `connected`, `no_address`, `no_key`, `refused` (`status` 401 or 403), `unavailable` (no answer, or an error with its `status`).
- Prowlarr: `version`, `count` the indexers on. qBittorrent: `version`, `count` the categories of shelfdrop found (`manga`, `ebook`, `audiobook`, `shelfdrop-manual`), `missing` the others. Jellyfin: `version`, `count` its libraries of books. A source: `elapsed_ms`, the time of a fixed search.

Errors: `422 invalid_settings` (an unknown service, or an address refused: `data.keys`).

## GET /api/v1/settings/health
The last tests of the background, run at start then every 5 minutes, of each service whose address and key are saved: `{"services": [<the object of the test>], "checked_at": 1792598400}`.

## GET /api/v1/settings/audit
The last 100 changes, the newest first: `{"entries": [{"at": 1792598400, "actor": "Sylvain", "action": "replaced", "target": "prowlarr.api_key"}]}`. `action`: `changed`, `replaced`, `cleared`, `imported` (`actor` `environment`); the target `trackers` or `filters` for a change of those.
