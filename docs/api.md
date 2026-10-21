# API

Every route but `/health` and the pages is served under the prefix `/api` (`SHELFDROP_API_PREFIX`). The API serves neither its schema nor a documentation page: this page describes it.

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

## GET /api/v1/works/{id}
A work a search returned in the last 7 days, the same object as an item of `works`. `404 work_not_found` otherwise.
