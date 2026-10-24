# 0008. Front-end and visible texts
Status: Accepted
Date: 2026-10-21

## Context
Decided at the start of the project: React and Tailwind, with strict TypeScript and ESLint rules; a panel served by the API itself; the texts impersonal, short and without technical sentences, following the rules of no-ai-slop.

## Decision
- `web/`: React, Vite, Tailwind, TypeScript strict, ESLint and Prettier, built by pnpm; the font Outfit is served from the build, never from a third party.
- The API serves the build: `assets/` and `fonts/` mounted, a file at the top of the build, otherwise `index.html` for any path outside the API.
- Every visible text is French, in `web/src/texts.ts` alone, and follows `docs/writing.md`.
- One address per section, read and written with the History API of the browser (`web/src/state/route.ts`, no router library): `/` (Automatique), `/manuel`, `/en-attente`, `/telechargements`, `/ranger`, `/jellyfin`, `/parametres`; a tab of the settings other than the first adds its slug (`/parametres/sources`, `recherche`, `filtres`, `rangement`, `discord`, `acces`, `journaux`). A change of section or of tab adds an entry to the history; Back and Forward change the view alone, the bar, the header and the frame stay. The links of the sidebar are real links (a new tab opens with the middle click). An unknown address, or one written otherwise (`/parametres/services`, a trailing slash), is replaced by the address of its view, the page Automatique when it has none.
- The search (its text, its kind, the work chosen, the releases checked) never goes into the address nor the history: leaving a page of search forgets it, coming back never runs it again; a search opened from En attente or Téléchargements adds the address of its page, then searches.

## Rejected alternatives
- A separate server for the pages: one more service and a cross-origin API.
- A router library for the addresses: seven sections and the tabs of one need the History API alone.
- The search in the address: the owner wants it forgotten when the page is left.

## Consequences
- The image builds the front-end in a Node stage and holds no Node.
- No address of a section is the name of a file at the top of the build (`index.html`, `favicon.svg`) nor starts with `assets/`, `fonts/` or the prefix of the API: the API answers `index.html` there (`tests/integration/test_pages.py`).
