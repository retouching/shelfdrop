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

Errors: `422 query_too_short`, `422 too_many_names`, `422 validation_failed`, `503 prowlarr_unavailable` (the trackers were never read and Prowlarr does not answer, or it is not configured).

## GET /api/v1/searches/{id}
The progress and the releases found so far, scored and ranked with the filters and the trackers of now; a search is kept 10 minutes after its end.

```json
{"progress": {...}, "minimum": -100, "releases": [
  {"id": "3f1c...", "title": "Jujutsu.Kaisen.T01.FRENCH.MANGA.CBZ.eBook-PapriKa+", "matched_name": "Jujutsu Kaisen",
   "indexer_id": 2, "indexer": "The Old School", "indexer_rank": 1, "info_url": "https://...", "info_hash": "...",
   "seeders": 30, "size": 99614720, "volumes": {"kind": "single", "first": 1, "last": 1},
   "score": 100, "score_rules": [{"name": "Français", "score": 100}], "rejected": null}]}
```

- In the order of the page: packs and complete editions first, then volume by volume; for one volume, the score, the order of the trackers, the seeds. No release without seeds; one found twice once.
- `volumes.kind`: `single`, `range`, `complete` or `unknown`.
- `rejected`: `relevance` (its title misses a word of its name), `score` (under `minimum`), or `null`.

Errors: `404 search_not_found`.

## GET /api/v1/searches/{id}/events
Server-Sent Events: a `progress` event (the object of `POST`) now and at each change, then an `end` event. `404 search_not_found`.

## GET /api/v1/trackers, POST /api/v1/trackers/refresh, PUT /api/v1/trackers
The indexers of Prowlarr, in their order: `{"trackers": [{"indexer_id": 1, "name": "Nyaa.si", "language": "en-US", "prowlarr_enabled": true, "used": true, "auto": true}]}`. `refresh` reads `GET /api/v1/indexer` of Prowlarr again (`503 prowlarr_unavailable`). `PUT` takes `{"trackers": [{"indexer_id", "used", "auto"}]}` in the new order; a tracker left out keeps its choices and comes after; a tracker not asked is never automatic.

## GET /api/v1/filters, PUT /api/v1/filters
`{"rules": [{"name": "Français", "pattern": "\\b(FRENCH|VF)\\b", "regex": true, "score": 100, "kinds": [], "enabled": true}], "minimum": -100}`. A rule of words matches whole words, any case, separated by commas; `kinds` empty: every kind. `PUT` replaces them; a rule whose expression is empty or invalid: `422 invalid_filter_rule`, `data.positions` its places, nothing saved.

## GET /api/v1/works/{id}
A work a search returned in the last 7 days, the same object as an item of `works`. `404 work_not_found` otherwise.
