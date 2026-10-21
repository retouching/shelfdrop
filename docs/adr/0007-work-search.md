# 0007. The work search
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user on 2026-10-21. A release is posted under one name among many (French, English, romaji): searching the indexers with the text typed alone missed releases, and once fetched the wrong manga ("Amnesia" for "Dusk Maiden of Amnesia"). The library must use the name of the French edition. MyAnimeList must be a source; if two people search the same title, one search must serve both.

## Decision
- A search asks every source of its family at once: MangaUpdates, Kitsu, MyAnimeList (through Jikan, without a Client ID), AniList and MangaDex for manga; Open Library and Wikidata for books; the BnF for both. A source that fails or takes more than 5 seconds is left out and named, and rests 5 minutes.
- The candidates merge by a shared id (the MyAnimeList id is the pivot), a shared ISBN, or a shared precise name with compatible authors and years. The name on the shelf is the title of the French edition at the BnF, otherwise a French, English or romaji name. At most 6 names are checked for the indexers.
- Two identical searches at the same time share one run; the answers of the sources are cached a day, the works a week, in SQLite.
- The two routes of the search are `async`: a search waits on every source at once on the event loop; the service runs the repository in the threadpool.
- The tests replay the real exchanges recorded from the sources; a failure at recording replays as a failure.

## Rejected alternatives
- Searching the indexers with the typed text alone: the mistake above.
- Hardcover: refused by the user.
- Sync routes with a thread per source: the search is I/O alone, and the event loop already runs it.

## Consequences
- AniList, MangaDex and MyAnimeList were down when the fixtures were recorded: the searches rest on MangaUpdates, Kitsu, Wikidata and the BnF for manga.
