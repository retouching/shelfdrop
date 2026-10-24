# 0017. The searches kept waiting
Status: Accepted
Date: 2026-10-21

## Context
Decided on 2026-10-21: a search can be kept waiting for a volume, chapters or any release, searched again at an interval of 1, 3, 6, 12 or 24 hours under every name of its work, in the queue of the other searches. A release that answers makes it « Trouvé », with a badge in the sidebar and a message on Discord; nothing is downloaded alone. A search of a volume leaves the list once the volume is placed; « Ch. 233 et suivants » stays, and moves to the first chapter not placed.

## Decision
- `waiting_searches` keeps each search: its work (its id, its name on the shelf, its author, its kind, the names searched), what it waits for (`any`, a `volume`, `chapters` from one to another or every one after), its state (`waiting`, `found` and the releases of its last search), its attempts, its last search, and when it left the list (`done_at`: removed, or placed).
- Several volumes make one search each; a search already waiting for the same work (by its id, else its name) and the same thing is not added again.
- The API runs the rounds (`WaitingRunner`, in the lifespan, every minute): the list tidied first, then each search due (never searched, or searched more than the interval ago, the setting `waiting.interval_hours`) searched one after another, through the search board of the page (`SearchBoard`, the queue and the cache of the other searches, the trackers checked, `refresh`). « Chercher maintenant » runs one at once.
- A release answers (`shelfdrop.waiting.matching.answers`) when the filters keep it (score, words, trackers) and it holds what is waited for: the volume (one, a pack around it, a complete edition), or a chapter of the range its name states (`Ch. 233`, `Chapitre 233`, `c233`, `#233`, `233-236`, `.5`), read as the search and the placement read them; any release kept for `any`.
- Found (from waiting): the event `found` of the journal (the work, what was waited for, the releases). Found again: no second message.
- Placed (the files of `files`, the placement of ADR 0016): a volume placed ends the search of it; chapters placed move the search of chapters to the first not placed (`233`, `234` placed: `235`), and end it past its last. A search of any release waits until removed.
- The page proposes the volumes not on the shelf: those placed, and those of the series of the same name in the library of its kind in Jellyfin (`LibraryReader.volumes_of`).

## Rejected alternatives
- A download of what is found: refused (« Rien n'est téléchargé seul »).
- The rounds in the placement worker: the searches share the queue and the cache of the board of the API.
- A search of every volume in one row: a volume found or placed could not leave the list alone.

## Consequences
- A search waits until removed, placed or found; a search found is searched again at the interval, and stays found while a release answers.
- A search of chapters without an end never leaves the list alone.
