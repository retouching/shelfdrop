# How it works

## Request lifecycle
A request goes through, from the outside in:
1. the wireup middleware, which opens the scope of the request (one database session, one `WorkService`);
2. `RequestIdMiddleware`: the `X-Request-ID` of the request and of its log records;
3. `AccessLogMiddleware`: one record per request, method, path, status and duration, never the query string nor a header;
4. `SecurityHeadersMiddleware`: the headers of [the API](api.md#responses);
5. `UnhandledErrorsMiddleware`: an unexpected exception becomes a logged `500 internal_error`;
6. `OriginMiddleware`: a write of the API without the `Origin` of its host gets `403 origin_refused`, unless it carries an `Authorization` header;
7. the route, after `require_session`, `require_reader` or `require_access` (every route of the API but the sign-in: [the session](#sign-in-and-sessions), or [an access token](#access-tokens)). After the response, `release_session` closes the session in the threadpool.

## Sign-in and sessions
`POST /api/v1/session` runs `shelfdrop.auth.service.AuthService.sign_in` ([ADR 0013](adr/0013-sign-in-and-sessions.md)):

1. **The attempts.** 5 a minute from one address, 30 an hour in all (`LoginThrottle`, in memory); past them, Jellyfin is not asked.
2. **Jellyfin.** The name and the password go to `POST /Users/AuthenticateByName`, at the address of the setting `jellyfin.url`, and nowhere else: never kept, never logged. Wrong credentials, an account that is not an administrator or is disabled: the same refusal, and the session Jellyfin opened is closed.
3. **The session.** A random token of 256 bits goes to the cookie; the database keeps its SHA-256, the account, and the access token of Jellyfin, sealed. 30 days.
4. **Each request.** The fingerprint of the cookie finds the session; when Jellyfin confirmed it 5 minutes ago or more, `GET /Users/Me` with its access token must give the same account, still an administrator, or the session ends. Jellyfin down: the request is refused, the session kept.

## Access tokens
A request with `Authorization: Bearer <secret>` is judged by its token alone ([ADR 0020](adr/0020-access-tokens.md), `shelfdrop.tokens.service.TokenService.check`): the SHA-256 of the secret finds a token neither revoked nor expired, it is counted (60 a minute), and its last use is written once a minute at most. The route then asks for its scope: none for a read, `write` for a write of the works, the downloads, Ranger, the uploads, the waiting searches or the page Jellyfin; the settings, the trackers, the filters and the tokens refuse every token.

## MCP server
`/mcp` is answered by `McpMiddleware`, inside the middlewares of the request id, the access log and the headers, before the routes ([ADR 0022](adr/0022-mcp-server.md)): the access token is checked as for the API, then the request goes to the MCP server of the SDK (stateless, one JSON answer per request). A tool opens a scope of the container of its own, calls the service of the route it mirrors (`WorkService.search`, `ReleaseService.start` then `watch` until the end, `DownloadService.send` under the name of the token...) and answers its schema; the tools that write refuse a token of reading.

## Release search
`POST /api/v1/searches` runs `shelfdrop.releases.service.ReleaseService.start` ([ADR 0011](adr/0011-release-search.md)):

1. **The trackers.** The indexers asked are those checked in the trackers and on in Prowlarr; at the first search, they are read from Prowlarr (`shelfdrop.releases.trackers`).
2. **One search per set of names.** `SearchBoard` joins the same search running (same mode, kind, names, trackers); a name two searches ask is one Prowlarr request. Each name is cleaned (`clean_query`), then read from the cache (`release_answers`, 10 minutes by default: the setting `search.release_cache_minutes`), otherwise queued: 2 requests at a time, first come first served, 60 seconds each at most. The search goes to its end even when nobody follows it; its progress goes to `GET .../events`.
3. **The releases** (`shelfdrop.releases.results.assemble`), at each read: no seed, out; the same guid or infohash, once, with its first name; in a work search, a title that misses a significant word of its name is set aside (`relevance`); the volumes are read from the title; the score is the sum of the points of the filter rules it matches (`shelfdrop.releases.scoring`), under the minimum it is set aside (`score`); a release kept, from a tracker whose `auto` is on, is `automatic`; then the order of the page.
4. **The torrent.** The download link Prowlarr gives a release is kept without its key, never sent to a page. `GET /api/v1/releases/{id}/torrent` finds the release in the searches kept and asks its link at the address of Prowlarr of the settings, the key in `X-Api-Key` (`ProwlarrClient.torrent`): the `.torrent` file, or a magnet link.

## Downloads
`POST /api/v1/downloads` runs `shelfdrop.downloads.service.DownloadService.send` ([ADR 0014](adr/0014-downloads.md)):

1. **The releases.** They are read from the search kept, scored with the filters and ranked with the trackers of now. The search of a work gives automatic downloads, which take only releases kept from a tracker whose `auto` is on; a manual search gives manual ones. Each release is a row of `downloads`: its work, its author, its series, its volumes, its kind, its category of qBittorrent, the account that sent it.
2. **The send**, after the answer (`shelfdrop.downloads.sender.DownloadSender`, 2 at a time): the torrent is asked to Prowlarr (`ProwlarrClient.torrent`) and its id read (`shelfdrop.utils.torrent`); qBittorrent, through qui, already lists it: a duplicate. Otherwise it is added into its category, then looked for by its hash 3 times, 8 seconds apart: found, sent; otherwise not received. The torrent is kept: a retry sends it again as it is.
3. **The follow-up.** `GET /api/v1/downloads` asks qBittorrent, in one request, for the downloads sent: their state, percent, speed and time left. A torrent complete is `completed` from then on: an automatic one waits for its placement, a manual one is to place in Ranger.
4. **A stop** during a send leaves it `sending`: it is sent again at start.

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

## Journal
Every process records its events in `events` as they happen (`shelfdrop.journal.service.Journal`), on a session of its own; a failure to record one is logged and never stops what it reports. The API posts them on the webhook of Discord (`JournalSender`, run by its lifespan) ([ADR 0015](adr/0015-journal.md)):

1. **The batches.** The events of one type and one group make one message: the volumes sent by one request (same account, same second, same work), the ends of the downloads of one request, the sign-ins of one account from one address, the attempts refused from one address. A batch is posted once its first event is 30 seconds old (`SHELFDROP_JOURNAL_BATCH_SECONDS`, a setting of the test stack).
2. **The message.** One embed (`shelfdrop.journal.embeds`): the French title of its type and its subject, the color of its type (the Radix palette of the pages), its fields, a link to `SHELFDROP_PUBLIC_URL`, the footer `shelfdrop` and the time of its last event. A cover recorded with an event (JPEG, PNG or WebP, 8 MB at most) is joined to the message (`attachment://cover.jpg`): the cover of the volume placed, and the cover of the work of an automatic download sent or complete, read once at its sources and joined to one event of each message of its request.
3. **The limits.** 5 messages a look, a look every 5 seconds; a `429` waits the seconds Discord asks (a minute at most) and the batch stays; a message that fails 3 times is dropped and logged. Without a webhook, or with its type switched off (`discord.events.<type>`), a batch is `skipped`.
4. **What goes there.** Never a secret nor a download link; a sign-in names the country Cloudflare gives it (`CF-IPCountry`), never its address nor the name typed.

## Placement
The worker `shelfdrop placement run` ([ADR 0016](adr/0016-placement.md)) runs a round every 30 seconds (`PlacementService.round`):

1. **The end.** The downloads `sent` qBittorrent has all of are `completed`, and each end goes once to the journal (`downloaded`), as when the page reads them.
2. **The files.** Each automatic download `completed`: its files are the `content_path` of its torrent in qBittorrent; none there: `missing_files`.
3. **The shelf compared.** A manga: the folder of its series is read, a volume there left (« Déjà présents »); a release in chapters is left to Ranger (`chapters`); a book without a volume read: `no_volume`. A book or an audiobook: a volume whose folder holds one is left; no author: `unknown_author`.
4. **The links.** Each file missing is hardlinked under its name of the shelf; nothing is replaced. The cover of a series without one: the first page of its first volume. The MP3 tracks of an audiobook: merged by ffmpeg into one M4B, its chapters one a track, its cover (the torrent, the tracks, the sources); the tracks of the shelf removed once merged; the page shows the percent.
5. **After.** The tag `placé` in qBittorrent, the scan of the library in Jellyfin, the download `placed` with its destination, the event `placed` with the cover; not placed: `to_place` with its reason (`failed` too for a link refused or a merge failed).
6. **The lock.** Each file placed that Jellyfin lists now (by its path, its library found by the name of its folder): its name, its series, its number and its authors set, `Name` and `Cast` locked.
7. **The writes asked.** The `cover.jpg` the page chose, written in the folder of its series.

## Ranger
After each round of the placement, the worker takes the files of Ranger ([ADR 0018](adr/0018-ranger.md), `HandPlacement.round`):

1. **Listed.** A download left to Ranger (`unplaced`, or manual and complete): its files read in its torrent, a release in chapters one file with its chapters, another one file a book (a folder of tracks for an audiobook).
2. **Placed.** What the page asked: a volume, a file of chapters, or the volumes of a release in chapters (a complete one merged into one CBZ, an incomplete one linked as it is, the rest without a volume or kept). A file of a download is hardlinked, one of the libraries moved; a name taken refuses (`exists`), nothing replaced. The download is `placed` once nothing of it is left.
3. **Scanned.** Once a day at `placement.scan_time`, and when the page asks: the files at the root of a library, out of their names, the folders of chapters and of MP3 tracks not merged; what the placement put there is left aside.
