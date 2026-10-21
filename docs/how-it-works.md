# How it works

## Request lifecycle
A request goes through, from the outside in:
1. the wireup middleware, which opens the scope of the request (one database session, one `WorkService`);
2. `RequestIdMiddleware`: the `X-Request-ID` of the request and of its log records;
3. `AccessLogMiddleware`: one record per request, method, path, status and duration, never the query string nor a header;
4. `SecurityHeadersMiddleware`: the headers of [the API](api.md#responses);
5. `UnhandledErrorsMiddleware`: an unexpected exception becomes a logged `500 internal_error`;
6. `OriginMiddleware`: a write of the API without the `Origin` of its host gets `403 origin_refused`;
7. the route, after `require_session` (every route of the API but the sign-in: [the session](#sign-in-and-sessions)). After the response, `release_session` closes the session in the threadpool.

## Sign-in and sessions
`POST /api/v1/session` runs `shelfdrop.auth.service.AuthService.sign_in` ([ADR 0013](adr/0013-sign-in-and-sessions.md)):

1. **The attempts.** 5 a minute from one address, 30 an hour in all (`LoginThrottle`, in memory); past them, Jellyfin is not asked.
2. **Jellyfin.** The name and the password go to `POST /Users/AuthenticateByName`, at the address of the setting `jellyfin.url`, and nowhere else: never kept, never logged. Wrong credentials, an account that is not an administrator or is disabled: the same refusal, and the session Jellyfin opened is closed.
3. **The session.** A random token of 256 bits goes to the cookie; the database keeps its SHA-256, the account, and the access token of Jellyfin, sealed. 30 days.
4. **Each request.** The fingerprint of the cookie finds the session; when Jellyfin confirmed it 5 minutes ago or more, `GET /Users/Me` with its access token must give the same account, still an administrator, or the session ends. Jellyfin down: the request is refused, the session kept.

## Release search
`POST /api/v1/searches` runs `shelfdrop.releases.service.ReleaseService.start` ([ADR 0011](adr/0011-release-search.md)):

1. **The trackers.** The indexers asked are those checked in the trackers and on in Prowlarr; at the first search, they are read from Prowlarr (`shelfdrop.releases.trackers`).
2. **One search per set of names.** `SearchBoard` joins the same search running (same mode, kind, names, trackers); a name two searches ask is one Prowlarr request. Each name is cleaned (`clean_query`), then read from the cache (`release_answers`, 10 minutes by default: the setting `search.release_cache_minutes`), otherwise queued: 2 requests at a time, first come first served, 60 seconds each at most. The search goes to its end even when nobody follows it; its progress goes to `GET .../events`.
3. **The releases** (`shelfdrop.releases.results.assemble`), at each read: no seed, out; the same guid or infohash, once, with its first name; in a work search, a title that misses a significant word of its name is set aside (`relevance`); the volumes are read from the title; the score is the sum of the points of the filter rules it matches (`shelfdrop.releases.scoring`), under the minimum it is set aside (`score`); a release kept, from a tracker whose `auto` is on, is `automatic`; then the order of the page.
4. **The torrent.** The download link Prowlarr gives a release is kept without its key, never sent to a page. `GET /api/v1/releases/{id}/torrent` finds the release in the searches kept and asks its link at the address of Prowlarr of the settings, the key in `X-Api-Key` (`ProwlarrClient.torrent`): the `.torrent` file, or a magnet link.

## Work search
`GET /api/v1/works?q=...&kind=...` runs `shelfdrop.works.service.WorkService.search`:

1. **The text.** Spaces are collapsed; below 2 letters or digits the search stops (`query_too_short`).
2. **One run per search.** Two identical searches at the same time (same kind, same normalized text) share one run: the second waits for the first and gets its answer (`SearchFlights`).
3. **The sources.** A manga search asks MangaUpdates, Kitsu, MyAnimeList (its official API, only with its Client ID), AniList and MangaDex; a book search asks Open Library and Wikidata; the BnF answers both; a source switched off in the settings is not asked. They are asked at once:
   - an answer of the last 24 hours (the setting `search.work_cache_hours`) is read from the cache instead;
   - a source that failed in the last 5 minutes is skipped;
   - a source that has not answered after 5 seconds, or answers an error, is left out, named in `unavailable` and rests 5 minutes.
   When every source of the family is left out, the search fails (`sources_unavailable`).
   After the merge, the BnF is asked again for the 3 best works it did not find, under a name of each (French, else romaji, else English, never the text already asked): "Battle Angel Alita" finds Gunnm at the other sources, and "Gunnm" its French edition at the BnF. These answers are cached the same way.
4. **The merge** (`shelfdrop.works.merge`). Every source gives candidates; two candidates are the same work when they share:
   - an id: a source and its id, or the id another source gives (Kitsu, AniList and MangaDex give the MyAnimeList id), or an ISBN;
   - or a name of 4 characters or more (abbreviations aside, a leading article ignored), with compatible authors (one shared word of 3 letters or more, since the sources disagree on the order of Japanese names) and years at most 2 apart (but for the BnF, which dates the French edition).
   The title, the authors and the form come from the most trusted source that has them (MyAnimeList, AniList, MangaUpdates, Kitsu, MangaDex, Open Library, Wikidata, BnF); the year is the earliest one, the BnF counting only when no other source has a year; the volumes of the original edition come from MangaUpdates, otherwise the highest count, those published in France from the BnF; the cover from Open Library, MangaUpdates, Kitsu, MyAnimeList or AniList.
5. **The names.** Every name once, with its best casing (the BnF writes titles in catalogue case) and its most precise language. A name no source gave a language for (MangaUpdates gives none) gets the one it shows, if any (`shelfdrop.works.names.language_of`): a language in brackets ("(Indonesian)"), letters only one language uses (Turkish `ı ş ğ`, Polish `ą ę ł`...), words made of Japanese syllables with a sign of them (a particle, an honorific, a long vowel: romaji), or the small words of one language (*the*, *of*; *le*, *des*; *der*, *das*...); otherwise it stays `latin`, unknown. The name on the shelf is the title of the French edition at the BnF, otherwise a French name, an English one, a romaji one, those a source gave before those guessed. At most 6 names are checked for the search in the indexers: French, then English, then romaji, a language a source gave before a guessed one; and the title of the work, whatever its language, so that a work always has one. Never an abbreviation, a name in another script, in another language or in none known (shown, unchecked), a part of a name already checked ("Chainsaw Man: Public Safety Saga") or the same name written together ("Chainsawman").
6. **The order** (`shelfdrop.works.ranking`). A work is kept when one of its names, or its authors, match the text well enough; an ISBN matches its work alone. The best match comes first, then a French name, the number of sources that agree, the popularity. For a manga search, novels, anthologies and dōjinshi go to `other_forms`. 12 works at most in each list.
7. **The cache.** The answers of the sources that answered are kept a day (by default), the works a week, in one transaction that also removes what expired. `GET /api/v1/works/{id}` reads a work kept there.

## Settings
The settings of the page and their secrets live in the database ([ADR 0012](adr/0012-settings-and-secrets.md), [the list](configuration.md#settings-of-the-page)). Each use reads them again (`shelfdrop.settings.reader.SettingsReader`): a search reads the sources switched on, the Client ID of MyAnimeList and the durations of the caches; each call of Prowlarr reads its address and its key, the key opened in memory for that call alone. At start, the values of the environment the database does not hold yet are imported, each once.

The tests of the connections (`shelfdrop.settings.probes.ConnectionProbes`) take the values typed on the page, or those saved: Prowlarr gives its version (`GET /api/v1/system/status`) and its indexers on; qBittorrent, reached through the client proxy of qui (`<address>/proxy/<key>`), its version and the categories `manga`, `ebook`, `audiobook`, `shelfdrop-manual`; Jellyfin its version (`GET /System/Info` with the key) and its libraries of books; a metadata source answers a fixed search ("Chainsaw Man", "Can't Hurt Me") in its time. `ConnectionMonitor`, started by the lifespan, tests at start then every 5 minutes each service whose address and key are saved; a failure is logged once, when it starts, and its end once. Every change of a setting, a secret, the trackers or the filters writes a line of `audit`: who, when, which key.
