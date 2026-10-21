# 0011. The release search
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user on 2026-10-21. A release is found only under the name it was posted under: a work is searched in Prowlarr under each of its names checked; searching a short name brought another manga ("Amnesia"). Two people who run the same search must follow one search; Prowlarr must not be flooded; the trackers must come from Prowlarr, not from the code; the user wants rules with points, as the custom formats of Sonarr, to set releases aside.

## Decision
- One Prowlarr request per name, in the categories of the kind (7030 manga, 7020 book, 3030 audiobook), on the trackers asked alone (`indexerIds`). The query loses `: ! ?` and quotes; "×" becomes "x".
- A search of a work sets aside a release whose title misses a significant word of the name that found it (3 letters or more, stop words aside); a manual search does not. Releases without seeds go; one found twice (same guid or infohash) is kept once, with its first name.
- The volumes are read from the title (`shelfdrop.releases.guess`). Order: packs first, then volume by volume; for one volume, the score, the order of the trackers, the seeds.
- The searches live in memory (`SearchBoard`, one process): the same search while it runs is joined; a name asked by two searches is one request; 2 requests at a time, the others in a queue, 60 seconds each at most; a search goes to its end without a follower. Each answer is kept 10 minutes in SQLite. The progress is streamed as Server-Sent Events.
- The score and the rejection by score are computed at each read, with the filters of now; the filters are rules of words or regular expressions with points, by kind, and a minimum score. A rule whose expression is invalid is refused at save.
- The trackers are read from `GET /api/v1/indexer`: torrent indexers alone; the first import orders Nyaa, The Old School, ABN, the others, C411 last, and leaves C411 out of the automatic downloads. A read again keeps the choices.
- Its routes are `async`, like those of the work search: the service holds the async client of Prowlarr, and runs the repository in the threadpool.
- The address and the key of Prowlarr, the number of names of a work search (6 by default) and the time an answer is kept (10 minutes by default) are settings, read at each use ([ADR 0012](0012-settings-and-secrets.md)).

## Rejected alternatives
- One request with every name: Prowlarr ORs nothing; a search per name is what the trackers understand.
- Scoring when the answer arrives: a change of the filters would wait 10 minutes.
- A list of trackers in the code: the user adds and removes indexers in Prowlarr.

## Consequences
- The front-end reads the releases only once the search ends; the events give the progress before.
- The rule expressions run in Python `re` on the server and in JavaScript in the page (the test field): a construct only one of them knows is refused or reads differently.
