# How it works

## Request lifecycle
A request goes through, from the outside in:
1. the wireup middleware, which opens the scope of the request (one database session, one `WorkService`);
2. `RequestIdMiddleware`: the `X-Request-ID` of the request and of its log records;
3. `AccessLogMiddleware`: one record per request, method, path, status and duration, never the query string nor a header;
4. `SecurityHeadersMiddleware`: the headers of [the API](api.md#responses);
5. `UnhandledErrorsMiddleware`: an unexpected exception becomes a logged `500 internal_error`;
6. the route. After the response, `release_session` closes the session in the threadpool.

## Work search
`GET /api/v1/works?q=...&kind=...` runs `shelfdrop.works.service.WorkService.search`:

1. **The text.** Spaces are collapsed; below 2 letters or digits the search stops (`query_too_short`).
2. **One run per search.** Two identical searches at the same time (same kind, same normalized text) share one run: the second waits for the first and gets its answer (`SearchFlights`).
3. **The sources.** A manga search asks MangaUpdates, Kitsu, MyAnimeList (its official API, only when `SHELFDROP_MYANIMELIST_CLIENT_ID` is set), AniList and MangaDex; a book search asks Open Library and Wikidata; the BnF answers both. They are asked at once:
   - an answer of the last 24 hours is read from the cache instead;
   - a source that failed in the last 5 minutes is skipped;
   - a source that has not answered after 5 seconds, or answers an error, is left out, named in `unavailable` and rests 5 minutes.
   When every source of the family is left out, the search fails (`sources_unavailable`).
4. **The merge** (`shelfdrop.works.merge`). Every source gives candidates; two candidates are the same work when they share:
   - an id: a source and its id, or the id another source gives (Kitsu, AniList and MangaDex give the MyAnimeList id), or an ISBN;
   - or a name of 4 characters or more (abbreviations aside, a leading article ignored), with compatible authors (one shared word of 3 letters or more, since the sources disagree on the order of Japanese names) and years at most 2 apart (but for the BnF, which dates the French edition).
   The title, the authors and the form come from the most trusted source that has them (MyAnimeList, AniList, MangaUpdates, Kitsu, MangaDex, Open Library, Wikidata, BnF); the year is the earliest one, the BnF counting only when no other source has a year; the volumes of the original edition come from MangaUpdates, otherwise the highest count, those published in France from the BnF; the cover from Open Library, MangaUpdates, Kitsu, MyAnimeList or AniList.
5. **The names.** Every name once, with its best casing (the BnF writes titles in catalogue case) and its most precise language. The name on the shelf is the title of the French edition at the BnF, otherwise a French name, an English one, a romaji one. At most 6 names are checked for the search in the indexers: French, then English, then romaji, never an abbreviation, a name in another script, a part of a name already checked ("Chainsaw Man: Public Safety Saga") or the same name written together ("Chainsawman").
6. **The order** (`shelfdrop.works.ranking`). A work is kept when one of its names, or its authors, match the text well enough; an ISBN matches its work alone. The best match comes first, then a French name, the number of sources that agree, the popularity. For a manga search, novels, anthologies and dōjinshi go to `other_forms`. 12 works at most in each list.
7. **The cache.** The answers of the sources that answered are kept a day, the works a week, in one transaction that also removes what expired. `GET /api/v1/works/{id}` reads a work kept there.
